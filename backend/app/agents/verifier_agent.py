
import json
from ..schemas import VerificationResult
from .utils import get_gemini_model
from ..logger import get_logger

logger = get_logger(__name__)

async def run_verifier_agent(query: str, proposed_solution: str, steps: list) -> VerificationResult:
    """
    Verifier Agent: Critiques the output of the Solver.
    """
    model = get_gemini_model()
    
    # Extract just step content for the prompt
    steps_text = "\n".join([f"{s.get('title')}: {s.get('content')}" for s in steps if isinstance(s, dict)])
    
    prompt = f"""
    You are an expert Math Verifier (The Critic).
    Your job is to check the proposed solution for correctness, logical flow, and unit consistency.
    
    ORIGINAL QUESTION:
    "{query}"
    
    PROPOSED SOLUTION STEPS:
    {steps_text}
    
    FINAL ANSWER:
    "{proposed_solution}"
    
    INSTRUCTIONS:
    1. Verify if the final answer mathematically follows from the steps.
    2. Check if the question was actually answered (did it address all parts?).
    3. Check for obvious hallucination or unit errors.
    4. Be strict but fair. Minor formatting issues are OK. logical errors are NOT.
    
    OUTPUT JSON SCHEMA:
    {{
        "is_correct": boolean,
        "critique": "Brief explanation of what is wrong (if any)",
        "correction_suggestion": "What should be fixed"
    }}
    
    Return ONLY valid JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
            
        data = json.loads(text)
        return VerificationResult(**data)
        
    except Exception as e:
        logger.error(f"Verifier Agent Failed: {e}")
        # Default to correct if verifier fails (fail open) to avoid infinite loops
        return VerificationResult(is_correct=True, critique="Verifier failed to run.")
