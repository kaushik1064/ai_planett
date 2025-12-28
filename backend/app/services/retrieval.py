"""Retrieval and routing logic for the math agent."""

from __future__ import annotations

from ..guardrails import GuardrailViolation
from ..logger import get_logger
from ..schemas import AgentResponse, Step
from ..workflows.langgraph_pipeline import build_math_agent_graph
from .vector_store import VectorStore, load_vector_store

logger = get_logger(__name__)


# Simple in-memory cache for HITL (Global for single-server deployment)
# In production, use Redis.
PENDING_CLARIFICATIONS: dict[str, str] = {}  # Global dict to store pending texts

from google.api_core.exceptions import ResourceExhausted

class MathAgent:
    """High-level orchestration for handling a math query."""

    def __init__(self, vector_store: VectorStore | None = None) -> None:
        self.vector_store = vector_store or load_vector_store()
        self.graph = build_math_agent_graph(self.vector_store)

    async def handle_query(self, query: str) -> AgentResponse:
        """Run the query through guardrails, routing, and generation."""
        
        # HITL Interception: Check if user is confirming a pending request
        # We treat "yes", "y", "correct", "sure" as confirmations if we have a pending text.
        # Since we don't have user_id, we use a single global slot "latest" for this demo.
        clean_q = query.strip().lower()
        if clean_q in ["yes", "y", "correct", "sure", "ok", "okay", "verify"] and "latest" in PENDING_CLARIFICATIONS:
            logger.info("math_agent.hitl_confirmed", original_query=query)
            query = PENDING_CLARIFICATIONS.pop("latest")
            # Proceed with the REPLACED query (the actual math problem)

        try:
            result_state = await self.graph.ainvoke({"query": query, "gateway_trace": []})
        except ResourceExhausted:
            logger.warning("math_agent.quota_exceeded")
            return AgentResponse(
                answer=" **System Overloaded (Rate Limit)** 🚦\n\nI'm receiving too many requests right now. Please wait 15-20 seconds and try again.\n(Google Gemini API Quota Exceeded)",
                steps=[],
                source="system_error"
            )
        except GuardrailViolation:
            raise
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("math_agent.graph_failure", error=str(exc))
            raise

        # HITL Check: Did the parser request clarification?
        structured = result_state.get("structured_problem")
        if structured and structured.needs_clarification:
            logger.info("math_agent.hitl_triggered", question=structured.clarification_question)
            
            # STORE the text so we remember it when user says "yes"
            PENDING_CLARIFICATIONS["latest"] = structured.cleaned_text
            
            return AgentResponse(
                answer=structured.clarification_question or "I need to clarify your request. Is the text correct?",
                steps=[Step(
                    title="Clarification Needed", 
                    content=f"I extracted this text from your image:\n\n**{structured.cleaned_text}**\n\nIs this correct? If not, please correct it below."
                )],
                feedback_required=True,
                source="parser_hitl"
            )

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
        
        # UI CLEANUP: If the answer is comprehensive (likely from Explainer with Markdown headers),
        # we suppress the raw technical steps to avoid "double vision" / bulkiness.
        is_comprehensive_explanation = len(answer_text) > 100 and ("##" in answer_text or "**Step" in answer_text)
        
        if not is_comprehensive_explanation:
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
            suppressed_steps=is_comprehensive_explanation
        )

        return response


