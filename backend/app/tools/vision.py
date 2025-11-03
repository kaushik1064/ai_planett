"""Image understanding helpers using Gemini multimodal models."""

from __future__ import annotations

import base64

import google.generativeai as genai

from ..config import settings


def _strip_data_url(data: str) -> str:
    if "," in data and data.startswith("data:"):
        return data.split(",", 1)[1]
    return data


def extract_text_from_image(image_base64: str, prompt: str = "Extract all mathematics text from this image.") -> str:
    """Use Gemini to extract math text from base64 encoded image."""

    if not settings.gemini_api_key:
        raise RuntimeError("Gemini API key not configured for image understanding")

    genai.configure(api_key=settings.gemini_api_key)
    clean_base64 = _strip_data_url(image_base64)
    image_bytes = base64.b64decode(clean_base64)
    model = genai.GenerativeModel(settings.gemini_model)
    response = model.generate_content(
        [prompt, {"mime_type": "image/png", "data": image_bytes}]
    )
    return response.text or ""


