"""Validation helpers for user-provided solutions."""

from __future__ import annotations

import google.generativeai as genai

from ..config import settings


def validate_user_solution(question: str, proposed_solution: str) -> bool:
    """Use Gemini to validate a user-uploaded solution."""

    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API key required for solution validation")

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model)
    prompt = (
        "You are an expert mathematics professor. Validate the student's solution. "
        "Return ONLY 'VALID' if the reasoning is mathematically correct. "
        "Return ONLY 'INVALID' otherwise.\n\n"
        f"Question: {question}\nStudent solution:\n{proposed_solution}"
    )
    response = model.generate_content(prompt)
    text = (response.text or "").strip().lower()
    return text.startswith("valid")


