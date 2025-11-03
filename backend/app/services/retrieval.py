"""Retrieval and routing logic for the math agent."""

from __future__ import annotations

from ..guardrails import GuardrailViolation
from ..logger import get_logger
from ..schemas import AgentResponse, Step
from ..workflows.langgraph_pipeline import build_math_agent_graph
from .vector_store import VectorStore, load_vector_store

logger = get_logger(__name__)


class MathAgent:
    """High-level orchestration for handling a math query."""

    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self.vector_store = vector_store or load_vector_store()
        self.graph = build_math_agent_graph(self.vector_store)

    async def handle_query(self, query: str) -> AgentResponse:
        """Run the query through guardrails, routing, and generation."""

        try:
            result_state = await self.graph.ainvoke({"query": query, "gateway_trace": []})
        except GuardrailViolation:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("math_agent.graph_failure", error=str(exc))
            raise

        steps_raw = result_state.get("steps", []) or []
        
        # Get KB hits and web hits separately, then combine for display
        kb_hits = result_state.get("kb_hits", []) or []
        web_hits = result_state.get("web_hits", []) or []
        # Combine for knowledge_hits display (show both KB and web)
        knowledge_hits = list(kb_hits) + list(web_hits)
        # If no separate hits, fall back to combined knowledge_hits
        if not knowledge_hits:
            knowledge_hits = result_state.get("knowledge_hits", []) or []
        
        citations = result_state.get("citations", []) or []
        answer_text = result_state.get("answer", "") or ""
        
        # If answer is too short (just overview), try to enhance it with steps
        if len(answer_text.strip()) < 50 and steps_raw:
            # Answer might be incomplete - use steps to build a better answer
            step_texts = []
            for step in steps_raw:
                if isinstance(step, dict):
                    step_texts.append(step.get("content", "") or step.get("explanation", ""))
                elif isinstance(step, (list, tuple)) and len(step) > 1:
                    step_texts.append(step[1])
            
            if step_texts:
                # Find the last step that looks like a conclusion
                for step_text in reversed(step_texts):
                    if any(word in step_text.lower() for word in ["therefore", "answer", "result", "thus", "hence"]):
                        answer_text = step_text
                        break
                
                # If still no good answer, use the last step
                if len(answer_text.strip()) < 50:
                    answer_text = step_texts[-1] if step_texts else answer_text
        
        retrieved_from_kb = result_state.get("retrieved_from_kb", False)
        source = result_state.get("source", "kb+web" if (kb_hits and web_hits) else ("kb" if retrieved_from_kb else "gemini"))
        gateway_trace = result_state.get("gateway_trace", [])

        # Convert steps to new format with content and optional expressions
        formatted_steps = []
        for step in steps_raw:
            # steps_raw is now a list of dicts with title/content/expression
            if isinstance(step, dict):
                formatted_steps.append(Step(
                    title=step.get("title", ""),
                    content=step.get("content", ""),
                    expression=step.get("expression")
                ))
            else:
                # Handle legacy tuple format for backward compatibility
                title, explanation = step
                formatted_steps.append(Step(
                    title=title,
                    content=explanation
                ))

        response = AgentResponse(
            answer=answer_text,
            steps=formatted_steps,
            retrieved_from_kb=retrieved_from_kb,
            knowledge_hits=knowledge_hits,
            citations=citations,
            source=source,
            gateway_trace=gateway_trace,
        )

        logger.info(
            "math_agent.completed",
            source=response.source,
            retrieved=retrieved_from_kb,
            kb_hits=len(knowledge_hits),
            trace=gateway_trace,
        )

        return response


