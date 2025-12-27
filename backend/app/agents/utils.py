
import google.generativeai as genai
from ..config import settings

def get_gemini_model(model_name: str = None):
    """Get a configured Gemini model instance."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set.")
    
    genai.configure(api_key=settings.gemini_api_key)
    
    model = model_name or settings.dspy_model
    return genai.GenerativeModel(model)
