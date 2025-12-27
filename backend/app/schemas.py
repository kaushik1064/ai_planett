"""Pydantic schemas for API endpoints."""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Step(BaseModel):
    """A solution step with title, content and optional LaTeX expression."""

    title: str
    content: str
    expression: Optional[str] = None


class Citation(BaseModel):
    """Represents a web citation."""

    title: str
    url: str


class RetrievalContext(BaseModel):
    """Context snippet from knowledge base."""

    document_id: str
    question: str
    answer: str
    similarity: float


class AgentResponse(BaseModel):
    """Structured agent response."""

    answer: str
    steps: List[Step]
    retrieved_from_kb: bool = False
    knowledge_hits: List[RetrievalContext] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    source: str = Field(default="kb")  # kb | tavily | gemini
    feedback_required: bool = True
    gateway_trace: List[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    """Incoming chat message payload."""

    query: str
    modality: str = Field(default="text", description="text|image|audio")
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None


class FeedbackMetadata(BaseModel):
    """User feedback payload."""

    # Minimal - Always Ask (5 seconds)
    thumbs_up: bool = Field(description="👍 Helpful / 👎 Not helpful")
    
    # If thumbs_down, expand to next level (10 seconds)
    primary_issue: Optional[str] = Field(
        None,
        description="What went wrong?",
        # These match exactly with the frontend enums
        enum=["wrong-answer", "unclear", "missing-steps", "wrong-method"]
    )
    
    # Optional user solution upload (30-60 seconds)
    has_better_solution: bool = False
    solution_type: Optional[str] = Field(
        None, 
        description="Type of solution upload",
        enum=["text", "pdf", "image"]
    )
    better_solution_text: Optional[str] = None
    better_solution_pdf_base64: Optional[str] = None
    better_solution_image_base64: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Feedback submission request."""

    message_id: str
    query: str
    agent_response: AgentResponse
    feedback: FeedbackMetadata


class BenchmarkResult(BaseModel):
    """Result for a single benchmark item."""

    question_id: str
    reference_answer: str
    agent_answer: str
    score: float
    source: str


class BenchmarkSummary(BaseModel):
    """Aggregate benchmark output."""

    dataset: str
    total_questions: int
    average_score: float
    details: List[BenchmarkResult]


class ErrorResponse(BaseModel):
    """Error response envelope."""

    detail: str
    code: str = Field(default="error")
    context: Optional[dict[str, Any]] = None



class StructuredProblem(BaseModel):
    """Output from Parser Agent."""
    original_text: str
    cleaned_text: str
    topic: str
    subtopic: Optional[str] = None
    problem_type: Optional[str] = None
    variables: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class VerificationResult(BaseModel):
    """Output from Verifier Agent."""
    is_correct: bool
    critique: Optional[str] = None
    correction_suggestion: Optional[str] = None
