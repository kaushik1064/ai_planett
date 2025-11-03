"""Guardrail functions for input/output moderation."""

from __future__ import annotations

import re
from typing import Tuple

from .config import settings
from .logger import get_logger

logger = get_logger(__name__)


class GuardrailViolation(Exception):
    """Raised when a guardrail condition is violated."""

    def __init__(self, message: str, code: str = "guardrail_violation") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


SANITIZE_REGEX = re.compile(r"[^\x20-\x7E]+")
PII_REGEX = re.compile(r"\b(\d{3}-?\d{2}-?\d{4}|\d{16}|[A-Z]{5}[0-9]{4}[A-Z]{1})\b")


def sanitize_text(text: str) -> str:
    """Remove non-ascii characters and collapse whitespace."""

    cleaned = SANITIZE_REGEX.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def run_input_guardrails(user_text: str) -> str:
    """Validate and sanitize user input before routing.
    
    Note: Since Gemini is used to validate math questions, we're very permissive here.
    Only block obvious non-math content and security issues.
    """

    logger.debug("guardrails.input.start", text=user_text)

    text = sanitize_text(user_text)

    # Only block PII - this is a security issue
    if PII_REGEX.search(text):
        logger.warning("guardrails.input.blocked", reason="pii_match")
        raise GuardrailViolation("The request may contain sensitive information. Please remove it and try again.")

    lower = text.lower()

    # Block only obvious non-educational content - let Gemini decide if it's math
    if any(keyword in lower for keyword in settings.blocked_keywords):
        logger.warning("guardrails.input.blocked", reason="blocked_keyword")
        raise GuardrailViolation("I can only help with mathematics-related educational questions.")

    # Very permissive - allow anything that could be math-related
    # Gemini will be the final validator, so we just do basic sanity checks
    # Allow anything with math-like patterns, or let it through and let Gemini decide
    
    logger.debug("guardrails.input.pass")
    return text


def run_output_guardrails(response_text: str) -> Tuple[str, list[str]]:
    """Apply output guardrails - very permissive since Gemini validates math content.
    
    Only blocks obvious non-math content. Most validation is done by Gemini.
    """

    logger.debug("guardrails.output.start")
    text = sanitize_text(response_text)

    citations: list[str] = []
    
    # Only block PII - security issue
    if PII_REGEX.search(text):
        logger.warning("guardrails.output.flag", reason="pii_detected")
        text = re.sub(PII_REGEX, "[redacted]", text)

    # Extract URLs as citations
    if "http" in text.lower():
        citations = re.findall(r"(https?://\S+)", text)

    # Very permissive - allow almost everything
    # Since Gemini generates the responses, it should be math-related
    # Only block if it's clearly and obviously non-math (e.g., contains blocked keywords)
    lower = text.lower()
    
    # Only block if it contains obviously inappropriate content
    if any(keyword in lower for keyword in settings.blocked_keywords):
        logger.warning("guardrails.output.blocked", reason="blocked_keyword", preview=text[:100])
        raise GuardrailViolation("The generated response contains inappropriate content.")

    # Everything else passes - let Gemini handle math validation
    logger.debug("guardrails.output.pass", citations=len(citations))
    return text, citations


