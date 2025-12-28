
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
    1.  **Layout**: Use `## Header` for each step. NEVER output a giant wall of text.
    2.  **Math**: Use LaTeX ($...$) for ALL math. Use `$$` for centered display equations.
        -   Good: $$ \int x^2 dx $$
        -   Bad: integral of x^2
    3.  **Tone**: Friendly and clear.
    4.  **No Redundancy**: Do not repeat "Step 1" if the header says "Step 1".
    
    ### FORMAT EXAMPLE (Follow this structure):
    
    ## Step 1: Analyze the Integral
    The problem asks us to evaluate:
    $$ \int \\frac{{\sec^2 x}}{{(\sec x + \tan x)^{{9/2}}}} dx $$
    
    ## Step 2: Choose Substitution
    Let's convert the terms. We know that:
    $$ \\frac{{d}}{{dx}}(\sec x + \tan x) = \sec x (\sec x + \tan x) $$
    
    ## Step 3: Solve
    Substituting back, we get:
    $$ -\\frac{{1}}{{7}} u^{{-7/2}} $$
    
    ### END EXAMPLE
    
    OUTPUT:
    A complete markdown string.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"Explainer Agent Failed: {e}")
        return solution # Fallback to raw solution
