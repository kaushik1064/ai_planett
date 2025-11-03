"""Audio transcription using Groq Whisper models."""

from __future__ import annotations

import base64
import io

from groq import Groq

from ..config import settings


def _strip_data_url(data: str) -> str:
    if "," in data and data.startswith("data:"):
        return data.split(",", 1)[1]
    return data


def transcribe_audio(audio_base64: str, language: str = "en") -> str:
    """Transcribe base64 encoded audio using Groq Whisper."""

    if not settings.groq_api_key:
        raise RuntimeError("GROQ_API_KEY not configured for speech transcription")

    client = Groq(api_key=settings.groq_api_key)
    clean_base64 = _strip_data_url(audio_base64)
    audio_bytes = base64.b64decode(clean_base64)
    audio_buffer = io.BytesIO(audio_bytes)
    audio_buffer.name = "input.wav"

    transcription = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo", file=audio_buffer, response_format="text", language=language
    )

    if hasattr(transcription, "text"):
        return transcription.text
    if isinstance(transcription, str):
        return transcription
    raise RuntimeError("Unexpected response format from Groq Whisper API")


