
import json
from typing import Any
from ..schemas import StructuredProblem
from .utils import get_gemini_model
from ..logger import get_logger

logger = get_logger(__name__)

async def run_parser_agent(query: str, modality: str = "text") -> StructuredProblem:
    """
    Parser Agent: Cleans and structures the raw input.
    """
    model = get_gemini_model()
    
    prompt = f"""
    You are an expert Math Problem Parser.
    Your job is to take a raw input string (which might be OCR'd text, ASR transcript, or typed text) and extract the structured math problem.
    
    INPUT:
    "{query}"
    
    MODALITY: {modality}
    
    INSTRUCTIONS:
    1. Fix any obvious OCR/ASR errors (e.g., '1' vs 'l', '0' vs 'O', 'sqrt' vs 'squirt').
    2. Extract the core math topic (e.g., Algebra, Calculus).
    3. Identify variables and constraints.
    4. CRITICAL: If MODALITY is "image", set "needs_clarification" to true to allow user verification.
    5. If the input is too ambiguous or nonsensical, set "needs_clarification" to true.
    
    OUTPUT JSON SCHEMA:
    {{
        "original_text": "{query}",
        "cleaned_text": "The fixed and clear math problem statement",
        "topic": "Broad topic",
        "subtopic": "Specific subtopic",
        "problem_type": "word_problem | calculation | proof | conceptual",
        "variables": ["x", "y"],
        "constraints": ["x > 0"],
        "needs_clarification": boolean,
        "clarification_question": "Please verify: Is this the correct problem?" (if image)
    }}
    
    Return ONLY valid JSON.
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        
        data = json.loads(text)
        
        # Validate with Pydantic
        return StructuredProblem(**data)
        
    except Exception as e:
        logger.error(f"Parser Agent Failed: {e}")
        # Fallback to simple structure
        return StructuredProblem(
            original_text=query,
            cleaned_text=query,
            topic="General",
            needs_clarification=False
        )
