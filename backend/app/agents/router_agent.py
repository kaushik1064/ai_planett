
import json
from .utils import get_gemini_model
from ..logger import get_logger

logger = get_logger(__name__)

async def run_router_agent(query: str) -> str:
    """
    Router Agent: Decides the workflow path.
    Returns: "solve", "search", or "general"
    """
    model = get_gemini_model()
    
    prompt = f"""
    You are an Intent Router.
    Classify the following user query into one of three categories:
    
    1. "solve": A specific math problem (algebra, word problem, calculus, etc.) that needs distinct solving steps.
    2. "search": A request for factual knowledge, definitions, history, or formulas (e.g., "Who invented calculus?", "Formula for area of circle").
    3. "general": Chit-chat, greetings, or non-math non-search queries (e.g., "Hi", "Help me").
    
    QUERY: "{query}"
    
    Return ONLY the category name (lowercase).
    """
    
    try:
        response = model.generate_content(prompt)
        category = response.text.strip().lower()
        
        if "solve" in category: return "solve"
        if "search" in category: return "search"
        return "general"
        
    except Exception as e:
        logger.error(f"Router Agent Failed: {e}")
        return "solve" # Default to solve
