"""LangGraph implementation of the math agent workflow."""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from ..config import settings
from ..guardrails import run_input_guardrails, run_output_guardrails
from ..logger import get_logger
from ..schemas import Citation, RetrievalContext
from ..services.vector_store import VectorStore
from ..tools.dspy_pipeline import SearchResult, generate_solution_with_cot
from ..tools.web_search import run_web_search_with_fallback

logger = get_logger(__name__)


class AgentGraphState(TypedDict, total=False):
    query: str
    sanitized_query: str
    gateway_trace: list[str]
    knowledge_hits: list[RetrievalContext]  # Combined KB + web for generation
    kb_hits: list[RetrievalContext]  # KB hits only (for UI)
    web_hits: list[RetrievalContext]  # Web hits only (for UI)
    search_result: SearchResult | None
    steps: list[tuple[str, str]]
    answer: str
    source: str
    citations: list[Citation]
    retrieved_from_kb: bool


def build_math_agent_graph(vector_store: VectorStore) -> StateGraph:
    """Compile the LangGraph workflow for the math agent."""

    graph = StateGraph(AgentGraphState)

    async def input_guardrails_node(state: AgentGraphState) -> AgentGraphState:
        sanitized = run_input_guardrails(state["query"]) if settings.enforce_input_guardrails else state["query"]
        trace = state.get("gateway_trace", []) + ["input_guardrails_pass"]
        return {"sanitized_query": sanitized, "gateway_trace": trace}

    async def retrieve_kb_node(state: AgentGraphState) -> AgentGraphState:
        query = state["sanitized_query"]
        kb_results = vector_store.search(query)
        kb_contexts: list[RetrievalContext] = []
        for result in kb_results:
            # kb_results is a list of dicts with: document_id, question, answer, source, similarity
            kb_contexts.append(
                RetrievalContext(
                    document_id=result.get("document_id", ""),
                    question=result.get("question", ""),
                    answer=result.get("answer", ""),
                    similarity=result.get("similarity", 0.0) or 0.0,
                )
            )
        trace = state.get("gateway_trace", []) + ["kb_search_complete"]
        # Store KB contexts separately so we can combine them later
        return {
            "knowledge_hits": kb_contexts, 
            "kb_hits": kb_contexts,  # Keep KB hits separate
            "gateway_trace": trace
        }

    def route_after_retrieval(state: AgentGraphState) -> Literal["kb", "search"]:
        # Always proceed to both KB and web search, then generate with Gemini
        # This ensures we always get comprehensive results
        contexts = state.get("knowledge_hits", []) or []
        if contexts and len(contexts) > 0:
            top_similarity = contexts[0].similarity if contexts[0].similarity is not None else 0.0
            if top_similarity >= settings.similarity_threshold:
                logger.info("router.has_good_kb_match", similarity=top_similarity, threshold=settings.similarity_threshold)
                # Still go to web search to enhance with additional context
                return "search"
            logger.info("router.kb_below_threshold", top_similarity=top_similarity, threshold=settings.similarity_threshold)
        else:
            logger.info("router.no_kb_results")
        # Always proceed to web search to get additional context
        return "search"

    async def kb_generation_node(state: AgentGraphState) -> AgentGraphState:
        # This node is deprecated - we now always go through web search then generation
        # But keep it for backward compatibility in case routing changes
        contexts = state.get("knowledge_hits", [])
        # Also fetch web search to combine with KB
        query = state["sanitized_query"]
        search_result = await run_web_search_with_fallback(query)
        web_contexts = []
        if search_result:
            web_contexts = [
                RetrievalContext(
                    document_id=document.id,
                    question=document.title,
                    answer=document.snippet,
                    similarity=document.score or 0.0,
                )
                for document in search_result.documents
            ]
        
        # Combine KB and web contexts
        all_contexts = contexts + web_contexts
        steps, answer_text = await generate_solution_with_cot(state["sanitized_query"], all_contexts, search_metadata=search_result)
        trace = state.get("gateway_trace", []) + ["router->kb+web"]
        return {
            "steps": steps,
            "answer": answer_text,
            "source": "kb+web",
            "retrieved_from_kb": True,
            "citations": state.get("citations", []),
            "gateway_trace": trace,
            "search_result": search_result,
        }

    async def web_search_node(state: AgentGraphState) -> AgentGraphState:
        query = state["sanitized_query"]
        # Get KB contexts from previous node (preserve them separately)
        kb_contexts = state.get("kb_hits", []) or state.get("knowledge_hits", [])
        
        # Always attempt web search
        search_result = await run_web_search_with_fallback(query)
        
        # Combine KB contexts with web search contexts for Gemini generation
        all_contexts = list(kb_contexts) if kb_contexts else []
        web_contexts = []
        
        if search_result and search_result.documents:
            web_contexts = [
                RetrievalContext(
                    document_id=document.id,
                    question=document.title,
                    answer=document.snippet,
                    similarity=document.score or 0.0,
                )
                for document in search_result.documents
            ]
            all_contexts.extend(web_contexts)
            
            citations = [
                Citation(title=document.title, url=document.url)
                for document in search_result.documents
                if document.url
            ]
            source = search_result.source
        else:
            logger.warning("web_search.no_results", query=query)
            citations = []
            source = "kb-only" if kb_contexts else "direct"
        
        trace = state.get("gateway_trace", []) + ["web_search_complete", f"source={source}"]
        return {
            "search_result": search_result,
            "knowledge_hits": all_contexts,  # Combined KB + web contexts for generation
            "kb_hits": kb_contexts,  # Keep KB hits separate for UI
            "web_hits": web_contexts,  # Keep web hits separate for UI
            "citations": citations,
            "retrieved_from_kb": len(kb_contexts) > 0,
            "source": source,
            "gateway_trace": trace,
        }

    async def search_generation_node(state: AgentGraphState) -> AgentGraphState:
        # Always use Gemini to generate comprehensive answer from all available contexts
        contexts = state.get("knowledge_hits", [])  # Already combined KB + web contexts
        search_metadata = state.get("search_result")
        
        logger.info("generation.starting", contexts_count=len(contexts), has_search_metadata=search_metadata is not None)
        
        try:
            # Always generate with Gemini using all available context
            steps, answer_text = await generate_solution_with_cot(
                state["sanitized_query"], 
                contexts, 
                search_metadata=search_metadata
            )
            
            # Ensure answer is comprehensive and not empty
            if not answer_text or not answer_text.strip():
                logger.warning("generation.empty_response", query=state["sanitized_query"])
                # Try to construct answer from steps if available
                if steps:
                    # Get the last step or combine all step content
                    if isinstance(steps[-1], dict):
                        answer_text = steps[-1].get("content", "") or steps[-1].get("explanation", "")
                    elif isinstance(steps[-1], (list, tuple)) and len(steps[-1]) > 1:
                        answer_text = steps[-1][1]
                    else:
                        answer_text = str(steps[-1])
                    
                    if not answer_text:
                        # Combine all step contents
                        answer_parts = []
                        for step in steps:
                            if isinstance(step, dict):
                                content = step.get("content", "") or step.get("explanation", "")
                                if content:
                                    answer_parts.append(content)
                            elif isinstance(step, (list, tuple)) and len(step) > 1:
                                answer_parts.append(step[1])
                        answer_text = "\n\n".join(answer_parts) if answer_parts else "Please see the steps above for the solution."
                else:
                    answer_text = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
                    steps = [{"title": "Error", "content": "Unable to generate solution with available context."}]
            
            # Log the response length to debug
            logger.info("generation.completed", answer_length=len(answer_text), steps_count=len(steps))
        except Exception as exc:
            logger.exception("generation.failed", error=str(exc))
            answer_text = "I encountered an error while processing your question. Please try again."
            steps = [{"title": "Error", "content": str(exc)}]
        
        # Always return with all context information - let UI decide what to show
        return {
            "steps": steps, 
            "answer": answer_text,
            # Keep all context for UI display
        }

    async def output_guardrails_node(state: AgentGraphState) -> AgentGraphState:
        if not settings.enforce_output_guardrails:
            return {}
        filtered_answer, urls = run_output_guardrails(state["answer"])
        citations = list(state.get("citations", []))
        for url in urls:
            if not any(citation.url == url for citation in citations):
                citations.append(Citation(title="Source", url=url))
        
        current_trace = state.get("gateway_trace", [])
        trace = current_trace + ["output_guardrails_pass"]
        
        return {"answer": filtered_answer, "citations": citations, "gateway_trace": trace}

    graph.add_node("input_guardrails", input_guardrails_node)
    graph.add_node("retrieve_kb", retrieve_kb_node)
    graph.add_node("kb_generate", kb_generation_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("search_generate", search_generation_node)
    graph.add_node("output_guardrails", output_guardrails_node)

    graph.set_entry_point("input_guardrails")
    graph.add_edge("input_guardrails", "retrieve_kb")
    graph.add_conditional_edges("retrieve_kb", route_after_retrieval, {"kb": "kb_generate", "search": "web_search"})
    graph.add_edge("kb_generate", "output_guardrails")
    graph.add_edge("web_search", "search_generate")
    graph.add_edge("search_generate", "output_guardrails")
    graph.add_edge("output_guardrails", END)

    return graph.compile()


