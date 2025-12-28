"""FastAPI entrypoint for the math agent backend."""

from __future__ import annotations

import asyncio
import os
from typing import AsyncIterator

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .guardrails import GuardrailViolation
from .logger import configure_logging, get_logger
from .schemas import AgentResponse, ChatRequest, FeedbackRequest
from .services.retrieval import MathAgent
from .services.vector_store import (
    load_vector_store,
    save_feedback_to_queue,
)
from .services.kb_updater import update_knowledge_base
from .tools.audio import transcribe_audio
from .tools.validator import validate_user_solution
from .tools.vision import extract_text_from_image
from .db import create_db_and_tables
from .routers import history

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(title=settings.app_name, version="0.1.0")

    # Configure CORS - Allow all for local dev to prevent "Failed to fetch"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(history.router)  # Register History API

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup
        logger.info("app.startup")
        create_db_and_tables()  # Initialize Supabase tables
        app.state.vector_store = await asyncio.to_thread(load_vector_store)
        
        yield  # Server is running
        
        # Shutdown
        logger.info("app.shutdown")
        # Clean up any resources if needed

    app.router.lifespan_context = lifespan

    def get_agent() -> MathAgent:
        vector_store = getattr(app.state, "vector_store", None)
        if vector_store is None:
            vector_store = load_vector_store()
            app.state.vector_store = vector_store
        return MathAgent(vector_store=vector_store)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        response.headers["X-App-Env"] = settings.environment
        return response

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    @app.post("/api/chat", response_model=AgentResponse, responses={400: {"description": "Guardrail failure"}})
    async def chat_endpoint(payload: ChatRequest, agent: MathAgent = Depends(get_agent)) -> AgentResponse:
        logger.info("chat.request", modality=payload.modality)

        query = payload.query
        if payload.modality == "audio" and payload.audio_base64:
            query = transcribe_audio(payload.audio_base64)
        elif payload.modality == "image" and payload.image_base64:
            query = extract_text_from_image(payload.image_base64)

        try:
            response = await agent.handle_query(query)
            return response
        except GuardrailViolation as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("chat.error", error=str(exc))
            raise HTTPException(status_code=500, detail="Unexpected error handling query") from exc

    @app.post("/api/feedback")
    async def feedback_endpoint(request: FeedbackRequest) -> JSONResponse:
        """Handle user feedback with optional solution upload."""
        logger.info(
            "feedback.received", 
            message_id=request.message_id,
            helpful=request.feedback.thumbs_up,
            issue=request.feedback.primary_issue
        )

        # Always save the feedback first
        record = request.model_dump()
        save_feedback_to_queue(record)

        # If it's negative feedback with a solution
        if not request.feedback.thumbs_up and request.feedback.has_better_solution:
            solution = None
            
            # Get solution based on type
            if request.feedback.solution_type == "text":
                solution = request.feedback.better_solution_text
            elif request.feedback.solution_type == "pdf":
                # TODO: Extract text from PDF
                solution = request.feedback.better_solution_text
            elif request.feedback.solution_type == "image":
                # Use vision model to extract solution from image
                if request.feedback.better_solution_image_base64:
                    solution = extract_text_from_image(
                        request.feedback.better_solution_image_base64,
                        "Extract the mathematical solution from this image."
                    )
            
            if solution:
                # Validate and update KB
                success = await update_knowledge_base(request.query, solution)
                return JSONResponse({
                    "status": "ok",
                    "feedback_saved": True,
                    "kb_updated": success
                })

        return JSONResponse({
            "status": "ok",
            "feedback_saved": True
        })

    @app.get("/api/vector-store/reload")
    async def reload_vector_store() -> dict[str, str]:
        app.state.vector_store = await asyncio.to_thread(load_vector_store, True)
        return {"status": "reloaded"}

    return app


app = create_app()


