"""LangGraph implementation of the Multi-Agent Math Mentor."""

from __future__ import annotations

from typing import Literal, TypedDict, List, Optional

from langgraph.graph import END, StateGraph

from ..config import settings
from ..guardrails import run_input_guardrails, run_output_guardrails
from ..logger import get_logger
from ..schemas import Citation, RetrievalContext, StructuredProblem
from ..services.vector_store import VectorStore
from ..tools.dspy_pipeline import SearchResult, generate_solution_with_cot
from ..tools.web_search import run_web_search_with_fallback

# Import new Agents
from ..agents.parser_agent import run_parser_agent
from ..agents.router_agent import run_router_agent
from ..agents.verifier_agent import run_verifier_agent
from ..agents.explainer_agent import run_explainer_agent

logger = get_logger(__name__)


class AgentGraphState(TypedDict, total=False):
    # Inputs
    query: str
    modality: str  # text, image, audio
    
    # Internal State
    sanitized_query: str
    structured_problem: StructuredProblem
    intent: str  # solve, search, general
    
    # Solver State
    knowledge_hits: list[RetrievalContext]
    kb_hits: list[RetrievalContext]
    web_hits: list[RetrievalContext]
    search_result: SearchResult | None
    
    # Solution State
    steps: list[tuple[str, str] | dict]
    answer: str  # The technical answer from Solver
    
    # Verification State
    is_correct: bool
    critique: str
    retry_count: int
    
    # Final Output
    final_solution_text: str  # The explained answer (mapped to 'answer' at end)
    steps_final: list[dict] # Final steps for UI
    source: str
    citations: list[Citation]
    retrieved_from_kb: bool
    gateway_trace: list[str]


def build_math_agent_graph(vector_store: VectorStore) -> StateGraph:
    """Compile the Multi-Agent LangGraph workflow."""

    graph = StateGraph(AgentGraphState)

    async def parser_node(state: AgentGraphState) -> AgentGraphState:
        """Agent 1: Parser - Cleans and structures the input."""
        query = state.get("query", "")
        modality = state.get("modality", "text")
        
        # 1. Input Guardrails (Legacy check first)
        sanitized = run_input_guardrails(query) if settings.enforce_input_guardrails else query
        
        # 2. Run Parser Agent
        problem = await run_parser_agent(sanitized, modality)
        
        trace = state.get("gateway_trace", []) + ["parser_agent_pass"]
        return {
            "sanitized_query": sanitized,
            "structured_problem": problem,
            "gateway_trace": trace,
            "retry_count": 0  # Initialize retry count
        }

    async def router_node(state: AgentGraphState) -> AgentGraphState:
        """Agent 2: Router - Decides the path."""
        problem = state["structured_problem"]
        
        # If parser flagged clarification, we might handle it here (future HITL)
        # For now, ask the Router Agent
        intent = await run_router_agent(problem.cleaned_text)
        
        trace = state.get("gateway_trace", []) + [f"router_decision={intent}"]
        return {"intent": intent, "gateway_trace": trace}

    async def retrieve_node(state: AgentGraphState) -> AgentGraphState:
        """Retrieval Step (Shared for Solver)."""
        query = state["structured_problem"].cleaned_text
        
        # 1. Vector Store Search
        kb_results = vector_store.search(query)
        kb_contexts = [
            RetrievalContext(
                document_id=r.get("document_id", ""),
                question=r.get("question", ""),
                answer=r.get("answer", ""),
                similarity=r.get("similarity", 0.0) or 0.0,
            ) for r in kb_results
        ]
        
        # 2. Web Search (Always run for robustness)
        search_result = await run_web_search_with_fallback(query)
        web_contexts = []
        citations = []
        if search_result and search_result.documents:
            web_contexts = [
                RetrievalContext(
                    document_id=d.id,
                    question=d.title,
                    answer=d.snippet,
                    similarity=d.score or 0.0,
                ) for d in search_result.documents
            ]
            citations = [Citation(title=d.title, url=d.url) for d in search_result.documents if d.url]

        all_contexts = kb_contexts + web_contexts
        
        trace = state.get("gateway_trace", []) + ["retrieval_complete"]
        return {
            "knowledge_hits": all_contexts,
            "kb_hits": kb_contexts,
            "web_hits": web_contexts,
            "search_result": search_result,
            "citations": citations,
            "retrieved_from_kb": len(kb_contexts) > 0,
            "gateway_trace": trace
        }

    async def solver_node(state: AgentGraphState) -> AgentGraphState:
        """Agent 3: Solver - Generates the solution (with Self-Correction)."""
        problem_text = state["structured_problem"].cleaned_text
        contexts = state.get("knowledge_hits", [])
        search_metadata = state.get("search_result")
        
        # Check if this is a retry
        critique = state.get("critique")
        if critique:
            logger.info("solver.retry_with_critique", critique=critique)
            problem_text += f"\n\nIMPORTANT: Previous attempt was incorrect. Critique: {critique}\nPlease fix this in the new solution."
        
        # Run Solver (DSPy implementation)
        steps, answer_text = await generate_solution_with_cot(problem_text, contexts, search_metadata)
        
        trace = state.get("gateway_trace", []) + ["solver_pass"]
        return {
            "steps": steps,
            "answer": answer_text,
            "source": "solver",
            "gateway_trace": trace
        }

    async def verifier_node(state: AgentGraphState) -> AgentGraphState:
        """Agent 4: Verifier - Checks the solution."""
        query = state["structured_problem"].cleaned_text
        answer = state["answer"]
        steps = state["steps"]
        
        verification = await run_verifier_agent(query, answer, steps)
        
        trace = state.get("gateway_trace", []) + [f"verification_pass={verification.is_correct}"]
        
        return {
            "is_correct": verification.is_correct,
            "critique": verification.critique,
            "gateway_trace": trace,
            "retry_count": state.get("retry_count", 0) + 1
        }
        
    async def explainer_node(state: AgentGraphState) -> AgentGraphState:
        """Agent 5: Explainer - Formats for the student."""
        query = state["structured_problem"].cleaned_text
        answer = state["answer"]
        steps = state["steps"]
        
        if state.get("intent") == "solve":
            final_explanation = await run_explainer_agent(query, answer, steps)
        else:
            final_explanation = answer # Just pass through for simple queries
            
        trace = state.get("gateway_trace", []) + ["explainer_pass"]
        
        # We need to map 'final_explanation' back to 'answer' because the API expects 'answer'
        # And we need to ensure 'steps' are in the right format
        
        # Format steps for UI if they came from Explainer (usually Explainer returns single text)
        # But our API expects 'steps' list.
        # Let's keep the original technical steps but use the Explanation as the Final Answer text?
        # Or better, wrap the explanation in a "Solution" step.
        
        return {
            "answer": final_explanation, # This overrides the technical answer with the friendly one
            "gateway_trace": trace
        }
    
    # --- Simple Nodes for Non-Math Intents ---
    
    async def general_chat_node(state: AgentGraphState) -> AgentGraphState:
        """Simple handler for chit-chat."""
        # Reuse solver for now but with no retrieval context, or simple prompt
        steps, answer = await generate_solution_with_cot(state["structured_problem"].cleaned_text, [])
        return {"answer": answer, "steps": steps, "gateway_trace": state.get("gateway_trace", []) + ["general_chat_pass"]}
        
    # --- Routing Logic ---
    
    def route_intent(state: AgentGraphState) -> str:
        return state["intent"]
        
    def route_verification(state: AgentGraphState) -> str:
        if state["is_correct"]:
            return "pass"
        if state["retry_count"] > 1: # Max 2 retries
            return "max_retries"
        return "fail"
        
    def route_parser(state: AgentGraphState) -> Literal["router", "end"]:
        """Check if clarification is needed."""
        if state["structured_problem"].needs_clarification:
            return "end"
        return "router"

    # --- Build Graph ---
    
    graph.add_node("parser", parser_node)
    graph.add_node("router", router_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("solver", solver_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("explainer", explainer_node)
    graph.add_node("general_chat", general_chat_node)
    
    # Entry
    graph.set_entry_point("parser")
    
    # Branching from Parser (HITL)
    graph.add_conditional_edges(
        "parser",
        route_parser,
        {
            "router": "router",
            "end": END
        }
    )
    
    # Branching from Router
    graph.add_conditional_edges(
        "router",
        route_intent,
        {
            "solve": "retrieve",
            "search": "retrieve", # Search also needs retrieval
            "general": "general_chat"
        }
    )
    
    # Main Math Pipeline
    graph.add_edge("retrieve", "solver")
    graph.add_edge("solver", "verifier")
    
    # Verification Loop
    graph.add_conditional_edges(
        "verifier",
        route_verification,
        {
            "pass": "explainer",
            "fail": "solver",      # LOOP BACK!
            "max_retries": "explainer" # Give up and show what we have
        }
    )
    
    # Converge
    graph.add_edge("explainer", END)
    graph.add_edge("general_chat", END)

    return graph.compile()
