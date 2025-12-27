
from .utils import get_gemini_model
from ..logger import get_logger

logger = get_logger(__name__)

async def run_explainer_agent(query: str, solution: str, steps: list) -> str:
    """
    Explainer Agent: Formats the solution into a friendly, student-centric response.
    """
    model = get_gemini_model()
    
    # Format steps for the context
    steps_text = ""
    for s in steps:
        if isinstance(s, dict):
            steps_text += f"{s.get('title')}: {s.get('content')}\n\n"
    
    prompt = f"""
    You are an Expert Math Tutor.
    Your job is to take a raw technical solution and explain it to a student clearly, with empathy.
    
    STUDENT QUESTION: "{query}"
    
    TECHNICAL SOLUTION:
    {steps_text}
    
    FINAL ANSWER: "{solution}"
    
    INSTRUCTIONS:
    1. Structure the response clearly with Markdown (## Headers, **Bold** terms).
    2. Start with a direct answer or brief summary.
    3. Explain the "Why" and "How" of the key steps. Don't just list numbers.
    4. Use friendly, encouraging tone ("Great question!", "Here is how we solve it").
    5. Use LaTeX for math expressions only if strictly necessary, but prefer readable text where possible.
    
    OUTPUT:
    A complete markdown string.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Explainer Agent Failed: {e}")
        return solution # Fallback to raw solution
