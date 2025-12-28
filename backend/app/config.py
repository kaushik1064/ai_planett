"""Application configuration using Pydantic settings."""

from functools import lru_cache
import os
from typing import List
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env path robustly so it works whether .env is at repo root or backend/.env
# This file is at backend/app/config.py → repo root is two levels up
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_DIR = _REPO_ROOT / "backend"
_ENV_CANDIDATES = [
    _REPO_ROOT / ".env",           # D:/ai_planet/.env
    _BACKEND_DIR / ".env",         # D:/ai_planet/backend/.env
    Path.cwd() / ".env",           # fallback to CWD
]
_ENV_FILE = next((p for p in _ENV_CANDIDATES if p.exists()), _REPO_ROOT / ".env")


class Settings(BaseSettings):
    """Runtime configuration loaded from environment or .env file."""

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="allow")

    app_name: str = "Math Agentic RAG"
    environment: str = "local"
    debug: bool = True

    # Vector store configuration (Weaviate)
    weaviate_url: str | None = None
    weaviate_api_key: str | None = None
    weaviate_collection: str = "mathvectors"  # Collection name in Weaviate cloud
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    top_k: int = 4
    similarity_threshold: float = 0.80

    # Guardrail keywords for allow-listing math topics
    allowed_subjects: List[str] = [
        "algebra",
        "geometry",
        "calculus",
        "probability",
        "statistics",
        "number theory",
        "trigonometry",
        "combinatorics",
        "math",
    ]

    blocked_keywords: List[str] = [
        "violence",
        "weapon",
        "politics",
        "hate",
        "self-harm",
        "explicit",
    ]

    # External service credentials
    tavily_api_key: str | None = None
    mcp_tavily_url: str | None = None  # e.g., https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-...
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    database_url: str | None = None  # Supabase Connection String

    # Model configuration
    gemini_model: str = "gemini-2.5-flash"  # Fast model for search grounding and vision
    dspy_model: str = "gemini-2.5-flash"    # For DSPy pipeline
    whisper_model: str = "whisper-large-v3-turbo"  # For audio transcription
    dspy_max_tokens: int = 2048

    # Feedback storage
    feedback_store_path: str = "backend/data/feedback_db.json"

    # Gateway / guardrails toggles
    enforce_input_guardrails: bool = True
    enforce_output_guardrails: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    settings = Settings()

    # Allow alternate env var aliases for KB similarity threshold
    # Priority: KB_SIMILARITY_THRESHOLD -> KB_THRESHOLD -> existing value
    kb_thresh_env = (
        os.getenv("KB_SIMILARITY_THRESHOLD")
        or os.getenv("KB_THRESHOLD")
    )
    if kb_thresh_env:
        try:
            settings.similarity_threshold = float(kb_thresh_env)
        except ValueError:
            # Ignore invalid values and keep existing
            pass

    return settings


settings = get_settings()


