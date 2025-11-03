"""Knowledge base update service for validated user solutions."""

from __future__ import annotations

import asyncio
from typing import Optional

from sentence_transformers import SentenceTransformer

from ..config import settings
from ..logger import get_logger
from ..tools.validator import validate_user_solution
from .vector_store import load_vector_store

logger = get_logger(__name__)


async def update_knowledge_base(question: str, solution: str, source: str = "user-feedback") -> bool:
    """Validate and add a new solution to the knowledge base."""
    
    try:
        # First validate the solution
        is_valid = await asyncio.to_thread(validate_user_solution, question, solution)
        
        if not is_valid:
            logger.warning("kb_update.validation_failed", question=question)
            return False
            
        # Load vector store
        vector_store = load_vector_store()
        encoder = SentenceTransformer(settings.embedding_model_name)
        
        # Generate embedding
        text = question + "\n" + solution
        embedding = encoder.encode(text)
        
        # Add to Weaviate
        data_object = {
            "question": question,
            "answer": solution,
            "source": source
        }
        
        # Add with vector
        vector_store.client.data_object.create(
            data_object=data_object,
            class_name=settings.weaviate_class_name,
            vector=embedding.tolist()
        )
        
        logger.info("kb_update.success", question=question, source=source)
        return True
        
    except Exception as exc:
        logger.error("kb_update.failed", error=str(exc), question=question)
        return False