"""DSPy powered reasoning pipeline for math explanations."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

# Normalization helpers to convert LaTeX-like math to readable text (module-wide)
_LATEX_SIMPLE_REPLACEMENTS = [
    (r"\\cdot", "·"),
    (r"\\times", "×"),
    (r"\\to", "→"),
    (r"\\leq", "≤"),
    (r"\\geq", "≥"),
    (r"\\neq", "≠"),
    (r"\\pm", "±"),
    (r"\\approx", "≈"),
    (r"\\infty", "∞"),
    (r"\\Rightarrow", "⇒"),
    (r"\\Leftarrow", "⇐"),
    (r"\\sin", "sin"),
    (r"\\cos", "cos"),
    (r"\\tan", "tan"),
    (r"\\ln", "ln"),
    (r"\\log", "log"),
    (r"\\lim", "lim"),
    (r"\\mathbb\{R\}", "R"),
    (r"\\mathbb\{R\}\^3", "R^3"),
    (r"\\mathbb\{Z\}", "Z"),
    (r"\\mathbb\{Q\}", "Q"),
    (r"\\sqrt", "√"),
    (r"\\pi", "π"),
    (r"\\theta", "θ"),
    (r"\\alpha", "α"),
    (r"\\beta", "β"),
    (r"\\gamma", "γ"),
    (r"\\Delta", "Δ"),
]

_FRAC_PATTERN = re.compile(r"\\frac\{([^}]+)\}\{([^}]+)\}")

def _normalize_math(text: str) -> str:
    if not text:
        return text
    # Remove inline/display math delimiters
    text = (
        text.replace("$$", "")
            .replace("$", "")
            .replace("\\[", "")
            .replace("\\]", "")
            .replace("\\(", "")
            .replace("\\)", "")
    )
    # Strip common markdown artifacts (bold/headers/backticks)
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"^\s*#{1,6}\s*", "", text, flags=re.MULTILINE)
    # Drop sizing/spacing commands
    text = re.sub(r"\\(left|right|big|Big|quad|qquad)\\?", "", text)
    # Replace \frac{a}{b} with (a)/(b)
    def _frac_sub(match: re.Match) -> str:
        return f"({match.group(1)})/({match.group(2)})"
    text = _FRAC_PATTERN.sub(_frac_sub, text)
    # Apply simple replacements
    for pattern, repl in _LATEX_SIMPLE_REPLACEMENTS:
        text = re.sub(pattern, repl, text)
    # Normalize powers and tidy operators spacing
    text = re.sub(r"\^2", "²", text)
    text = re.sub(r"\^3", "³", text)
    text = re.sub(r"\s*([=+\-×·*/])\s*", r" \1 ", text)
    # Collapse excessive spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

try:
    import dspy  # type: ignore
    import google.generativeai as genai  # type: ignore

    from ..config import settings
    from ..logger import get_logger

    logger = get_logger(__name__)

    class GeminiLM(dspy.LM):
        """Minimal DSPy LM wrapper around Gemini API."""

        def __init__(self, model: str, api_key: str, max_output_tokens: int = 2048) -> None:
            super().__init__(model=model, max_output_tokens=max_output_tokens)
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model)

        def __call__(self, prompt: str, **kwargs) -> dspy.Completion:
            response = self._model.generate_content(prompt)
            text = response.text or ""
            return dspy.Completion(text=text)

        def loglikelihood(self, prompt: str, continuation: str) -> float:
            raise NotImplementedError("GeminiLM.loglikelihood is not supported")


    class MathTutorSignature(dspy.Signature):
        """DSPy signature describing the desired behavior."""

        query = dspy.InputField(desc="Student's mathematics question - MUST solve completely")
        context = dspy.InputField(desc="Knowledge snippets retrieved from KB or web")
        requirements = dspy.InputField(desc="JSON encoded requirements for the explanation")
        solution = dspy.OutputField(desc="Structured JSON with COMPLETE solution including all steps, all parts answered, and explicit final answer. Must be a complete solution, not just an overview.")


    def _ensure_dspy_configured() -> None:
        if settings.gemini_api_key is None:
            raise RuntimeError("Gemini API key missing. Set GEMINI_API_KEY in environment.")

        lm = GeminiLM(model=settings.dspy_model, api_key=settings.gemini_api_key, max_output_tokens=settings.dspy_max_tokens)
        dspy.settings.configure(lm=lm)


    @dataclass
    class WebDocument:
        id: str
        title: str
        url: str
        snippet: str
        score: float


    @dataclass
    class SearchResult:
        query: str
        source: str
        documents: Sequence[WebDocument]


    async def generate_solution_with_cot(
        query: str,
        contexts: Iterable,
        search_metadata: SearchResult | None = None,
    ) -> tuple[list[tuple[str, str]], str]:
        """Return (steps, final_answer) produced by Gemini via DSPy."""

        _ensure_dspy_configured()

        context_blocks: List[str] = []
        for ctx in contexts:
            block = json.dumps({
                "document_id": getattr(ctx, "document_id", ""),
                "question": getattr(ctx, "question", ""),
                "answer": getattr(ctx, "answer", ""),
                "similarity": getattr(ctx, "similarity", 0.0),
            }, ensure_ascii=False)
            context_blocks.append(block)

        if search_metadata:
            citations = [doc.__dict__ for doc in search_metadata.documents]
        else:
            citations = []

        requirements = {
            "style": "Explain as a friendly mathematics professor using numbered steps.",
            "must_include": [
                "Start the response with a single line: 'Answer: <final value or statement>'",
                "You MUST solve the ENTIRE problem completely - do not stop with just an overview",
                "List each algebraic manipulation explicitly",
                "Show ALL intermediate steps - do not skip any calculations",
                "Conclude with a clear final numeric or symbolic answer",
                "If the problem has multiple parts, answer ALL parts and label them (a), (b), etc.",
                "Avoid LaTeX markers like $...$ or \\frac{}{}; prefer natural language and simple unicode math",
                "State units or interpretation when relevant (probability, geometry, word problems, etc.)",
            ],
            "citations": citations,
        }

        # Build comprehensive context prompt
        context_prompt = ""
        if context_blocks:
            context_prompt = "\n\nCONTEXT FROM KNOWLEDGE BASE AND WEB SEARCH:\n" + "\n".join(context_blocks)
        
        enhanced_query = (
            f"{query}\n\n"
            "IMPORTANT: Solve this problem COMPLETELY. Provide all steps and the final answer. "
            "Do not just give an overview - actually solve the entire problem." + context_prompt
        )

        predictor = dspy.Predict(MathTutorSignature)

        async def _run_predict() -> dspy.Prediction:
            return await asyncio.to_thread(
                predictor,
                query=enhanced_query,
                context="\n".join(context_blocks) if context_blocks else "No additional context available.",
                requirements=json.dumps(requirements, ensure_ascii=False),
            )

        prediction = await _run_predict()

        try:
            structured = json.loads(prediction.solution)
        except json.JSONDecodeError:
            logger.warning("dspy.solution.parse_failed", solution_preview=prediction.solution[:200] if prediction.solution else "")
            # Try to extract solution from non-JSON response
            solution_text = _normalize_math(prediction.solution or "")
            # If it's not JSON, treat it as a natural language response and parse it
            structured = {
                "steps": [
                    {
                        "title": "Complete Solution",
                        "explanation": solution_text,
                    }
                ],
                "final_answer": solution_text.split("\n")[-1] if "\n" in solution_text else solution_text,
            }

        steps_raw = structured.get("steps", [])
        
        # Convert to dict format if it's tuple format
        steps = []
        for idx, step in enumerate(steps_raw):
            if isinstance(step, dict):
                steps.append({
                    "title": step.get("title", f"Step {idx+1}"),
                    "content": _normalize_math(step.get("explanation", step.get("content", ""))),
                    "expression": _normalize_math(step.get("expression")) if step.get("expression") else None
                })
            elif isinstance(step, (list, tuple)) and len(step) >= 2:
                steps.append({
                    "title": step[0],
                    "content": _normalize_math(step[1]),
                    "expression": _normalize_math(step[2]) if len(step) > 2 and step[2] else None
                })
            else:
                steps.append({
                    "title": f"Step {idx+1}",
                    "content": _normalize_math(str(step)),
                    "expression": None
                })
        
        final_answer = _normalize_math(structured.get("final_answer", ""))
        
        # Ensure final_answer is not empty
        if not final_answer and steps:
            # Try to extract from last step
            last_content = steps[-1].get("content", "")
            if last_content:
                # Look for answer patterns
                for line in reversed(last_content.split("\n")):
                    if any(word in line.lower() for word in ["answer", "therefore", "thus", "hence", "result"]):
                        final_answer = _normalize_math(line)
                        break
                if not final_answer:
                    final_answer = last_content.split("\n")[-1] if "\n" in last_content else last_content
        
        # Ultimate fallback
        if not final_answer:
            final_answer = "Please see the steps above for the complete solution."

        # Prepend a single-line explicit answer for UI readability
        if not final_answer.lower().startswith("answer:"):
            final_answer = f"Answer: {final_answer}"

        return steps, final_answer
except Exception:  # pragma: no cover - fallback when dspy isn't installed
    # Provide a lightweight fallback so the application can start even if
    # `dspy` is not installed. This fallback uses the Gemini client directly
    # to generate a JSON-structured explanation.
    import google.generativeai as genai  # type: ignore

    from ..config import settings
    from ..logger import get_logger

    logger = get_logger(__name__)


    @dataclass
    class WebDocument:
        id: str
        title: str
        url: str
        snippet: str
        score: float


    @dataclass
    class SearchResult:
        query: str
        source: str
        documents: Sequence[WebDocument]


    async def generate_solution_with_cot(
        query: str,
        contexts: Iterable,
        search_metadata: SearchResult | None = None,
    ) -> tuple[list[dict[str, str]], str]:
        """Fallback: use Gemini directly to produce a JSON with `steps` and `final_answer`.

        This is intentionally simple: it asks the model to return a JSON object. If parsing
        fails, we return the raw text as a single reasoning step.
        """

        if settings.gemini_api_key is None:
            raise RuntimeError("Gemini API key missing. Set GEMINI_API_KEY in environment.")

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.dspy_model)

        context_text = []
        for ctx in contexts:
            context_text.append(json.dumps({
                "document_id": getattr(ctx, "document_id", ""),
                "question": getattr(ctx, "question", ""),
                "answer": getattr(ctx, "answer", ""),
                "similarity": getattr(ctx, "similarity", 0.0),
            }, ensure_ascii=False))

        context_section = ""
        if context_text:
            context_section = "\n\nCONTEXT FROM KNOWLEDGE BASE AND WEB SEARCH:\n" + "\n".join(context_text) + "\n"
        
        prompt = (
            "You are an expert mathematics tutor across ALL math domains (arithmetic, algebra, geometry, trigonometry, calculus, linear algebra, probability, statistics, number theory, optimization, etc.). Provide clear, human-friendly solutions.\n\n"
            "CRITICAL REQUIREMENTS - YOU MUST FOLLOW THESE:\n"
            "1. Start your response with a single line: 'Answer: <final value or statement>'.\n"
            "2. Solve the ENTIRE problem - do NOT just give an overview or stop midway.\n"
            "3. Show EVERY step of your work - no skipped calculations.\n"
            "4. If there are multiple parts, answer ALL parts, labeled (a), (b), etc.\n"
            "5. Provide a clear, explicit FINAL ANSWER at the very end as well.\n"
            "6. Avoid LaTeX markers like $...$ or \\frac{}{}; write math in natural language or simple unicode (e.g., 1/2, ·, ×, →).\n"
            "7. Use concise, readable sentences; keep symbols understandable to non-experts.\n\n"
            "RESPONSE STRUCTURE:\n"
            "1. Brief Overview (1-2 sentences about the goal)\n"
            "2. Step-by-Step Solution (numbered) with clear titles and calculations\n"
            "3. Final Answer Section (repeat the answer clearly)\n\n"
            "STUDENT'S QUESTION:\n" + query + context_section +
            "\n\nNOW SOLVE THIS PROBLEM COMPLETELY.\n"
        )

        # Generate with more tokens to ensure complete answers
        from google.generativeai.types import GenerationConfig
        
        generation_config = GenerationConfig(
            temperature=0.3,  # Lower temperature for more focused responses
            max_output_tokens=8192,  # Increased for complete solutions
            top_p=0.95,
        )
        
        resp = model.generate_content(prompt, generation_config=generation_config)
        text = (resp.text or "").strip()
        text = _normalize_math(text)
        
        if not text:
            logger.warning("dspy.fallback.empty_response", query=query)
            text = "I apologize, but I couldn't generate a response. Please try rephrasing your question."

        try:
            # Parse the natural language response into structured steps
            lines = text.strip().split("\n")
            steps = []
            current_step = None
            final_answer = ""
            buffer = []
            overview_added = False

            for line in lines:
                line = line.strip()
                if not line:
                    if current_step and buffer:
                        current_step["content"] = "\n".join(buffer)
                        buffer = []
                    continue

                # Detect step headers (more flexible patterns)
                step_match = False
                if line.lower().startswith("step ") or re.match(r"^\d+[\.\)]\s+", line, re.IGNORECASE):
                    step_match = True
                    if current_step:
                        current_step["content"] = "\n".join(buffer)
                        steps.append(current_step)
                        buffer = []
                    # Extract step number and title
                    step_parts = re.split(r"[:\.]", line, 1)
                    step_title = step_parts[1].strip() if len(step_parts) > 1 else line
                    current_step = {
                        "title": step_title if step_title else f"Step {len(steps) + 1}",
                        "content": "",
                        "expression": None
                    }
                # Detect final answer section
                elif any(word in line.lower() for word in ["therefore", "thus", "finally", "hence", "answer:", "the answer is", "final answer"]):
                    if current_step:
                        current_step["content"] = "\n".join(buffer)
                        steps.append(current_step)
                        buffer = []
                        current_step = None
                    # Extract final answer
                    for word in ["therefore", "thus", "finally", "hence", "answer:", "the answer is", "final answer"]:
                        if word in line.lower():
                            final_answer = line.split(":", 1)[1].strip() if ":" in line else line
                            break
                    if not final_answer:
                        final_answer = line
                # Handle equations (lines with = or mathematical operators)
                elif current_step and ("=" in line or any(s in line for s in "+-*/^√∫∑∈ℝ")):
                    if buffer:  # Save accumulated explanation first
                        current_step["content"] = "\n".join(buffer)
                        buffer = []
                    if not current_step["expression"]:
                        current_step["expression"] = _normalize_math(line)
                    else:
                        current_step["expression"] += "\n" + _normalize_math(line)
                # Add to current step's content
                elif current_step:
                    buffer.append(line)
                # Handle text before first step (overview)
                elif not overview_added and not step_match:
                    steps.append({
                        "title": "Overview",
                        "content": line,
                        "expression": None
                    })
                    overview_added = True

            # Don't forget the last step
            if current_step:
                if buffer:
                    current_step["content"] = "\n".join(buffer)
                steps.append(current_step)

            # If no steps were parsed, create steps from the text
            if not steps:
                # Split by paragraphs or double newlines
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                for idx, para in enumerate(paragraphs):
                    if idx == 0:
                        steps.append({
                            "title": "Solution",
                            "content": _normalize_math(para),
                            "expression": None
                        })
                    else:
                        steps.append({
                            "title": f"Step {idx}",
                            "content": _normalize_math(para),
                            "expression": None
                        })

            # Extract final answer if not found
            if not final_answer:
                # Look for answer patterns in the last few lines
                for line in reversed(lines[-10:]):
                    line_lower = line.lower()
                    if any(word in line_lower for word in ["answer", "therefore", "thus", "hence", "result"]):
                        final_answer = line
                        break
                
                # If still no answer, use the last meaningful line or paragraph
                if not final_answer and steps:
                    last_content = steps[-1].get("content", "")
                    if last_content:
                        final_answer = last_content.split("\n")[-1] if "\n" in last_content else last_content
                
                # Ultimate fallback
                if not final_answer:
                    final_answer = "Please refer to the steps above for the complete solution."

            return steps, final_answer
        except Exception:
            logger.warning("dspy.fallback.parse_failed")
            # Even for plain text, maintain consistent structure
            return [{
                "title": "Solution",
                "content": text
            }], text


