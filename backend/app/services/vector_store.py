"""Vector store utilities using Weaviate cloud for knowledge base retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import weaviate
from sentence_transformers import SentenceTransformer
from weaviate.collections.classes.config import DataType

from ..config import settings
from ..logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Wrapper around Weaviate vector store."""

    def __init__(self, client: weaviate.WeaviateClient, encoder: SentenceTransformer) -> None:
        self.client = client
        self.encoder = encoder
        self.collection = self._ensure_collection()
        self._property_map = self._detect_property_names()

    def _ensure_collection(self) -> weaviate.collections.Collection:
        """Create collection if it doesn't exist."""
        collection_name = settings.weaviate_collection
        collections = self.client.collections.list_all()

        # Check for exact or case-insensitive match to avoid 422 when class
        # already exists with different casing (e.g. 'Mathvectors').
        lower_names = [n.lower() for n in collections]
        if collection_name not in collections and collection_name.lower() not in lower_names:
            try:
                collection = self.client.collections.create(
                    name=collection_name,
                    vectorizer_config=weaviate.classes.config.Configure.Vectorizer.none(),
                    vector_index_config=weaviate.classes.config.Configure.VectorIndex.hnsw(),
                    properties=[
                        {"name": "question", "data_type": DataType.TEXT},
                        {"name": "answer", "data_type": DataType.TEXT},
                        {"name": "source", "data_type": DataType.TEXT},
                    ]
                )
                logger.info("vector_store.collection.created", name=collection_name)
            except weaviate.exceptions.UnexpectedStatusCodeError as e:
                # If the create failed because the class already exists (422),
                # recover by locating the existing class name (case-insensitive)
                msg = str(e)
                if "already exists" in msg or "class name" in msg:
                    logger.warning("vector_store.collection.create_conflict", msg=msg)
                    # refresh list and try to find the existing class name
                    collections = self.client.collections.list_all()
                    existing = None
                    for n in collections:
                        if n.lower() == collection_name.lower():
                            existing = n
                            break
                    if existing:
                        collection = self.client.collections.get(existing)
                        logger.info("vector_store.collection.exists", name=existing)
                    else:
                        # re-raise if we can't resolve the conflict
                        raise
                else:
                    raise
        else:
            # exact or case-insensitive match found — pick the actual existing name
            if collection_name in collections:
                existing_name = collection_name
            else:
                existing_name = next(n for n in collections if n.lower() == collection_name.lower())
            collection = self.client.collections.get(existing_name)
            logger.info("vector_store.collection.exists", name=existing_name)

        return collection

    def _detect_property_names(self) -> Dict[str, str]:
        """Detect the actual property names in the collection schema.
        
        Returns a mapping from logical names (question, answer, source) to actual property names.
        """
        property_map = {}
        prop_names = []
        
        try:
            # Get the collection configuration to see what properties exist
            config = self.collection.config.get()
            
            # Try different ways to access properties depending on Weaviate v4 structure
            if hasattr(config, 'properties'):
                props = config.properties
                if props:
                    # Properties might be a list or iterable
                    if isinstance(props, (list, tuple)):
                        prop_names = [prop.name if hasattr(prop, 'name') else str(prop) for prop in props]
                    elif hasattr(props, '__iter__') and not isinstance(props, (str, bytes)):
                        prop_names = [prop.name if hasattr(prop, 'name') else str(prop) for prop in props]
            
            # Also try accessing as attributes
            if not prop_names and hasattr(config, 'properties'):
                try:
                    props_dict = config.properties.__dict__ if hasattr(config.properties, '__dict__') else {}
                    prop_names = list(props_dict.keys()) if props_dict else []
                except:
                    pass
            
        except Exception as exc:
            logger.warning("vector_store.schema.detection_error", error=str(exc))
        
        # Try to map to our expected names
        # Check for new schema (question, answer, source) first
        if prop_names:
            if "question" in prop_names:
                property_map["question"] = "question"
            elif "input" in prop_names:
                property_map["question"] = "input"
            
            if "answer" in prop_names:
                property_map["answer"] = "answer"
            elif "label" in prop_names:
                property_map["answer"] = "label"
            
            if "source" in prop_names:
                property_map["source"] = "source"
            elif "source_file" in prop_names:
                property_map["source"] = "source_file"
        else:
            # No properties detected - use fallback (old schema)
            logger.warning("vector_store.schema.detection_failed", msg="Could not detect properties, using fallback")
            property_map = {"question": "input", "answer": "label", "source": "source_file"}
        
        # If detection partially failed, fill in missing mappings
        if "question" not in property_map:
            property_map["question"] = "input"
        if "answer" not in property_map:
            property_map["answer"] = "label"
        if "source" not in property_map:
            property_map["source"] = "source_file"
        
        logger.info("vector_store.schema.detected", mapping=property_map, found_properties=prop_names)
        return property_map

    def search(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:
        """Search for similar questions and return contexts."""
        if top_k is None:
            top_k = settings.top_k

        # Generate embedding for query
        embedding = self.encoder.encode(query)
        embedding = embedding / np.linalg.norm(embedding)  # Normalize

        try:
            # Get the actual property names from the detected schema
            question_prop = self._property_map.get("question", "input")
            answer_prop = self._property_map.get("answer", "label")
            source_prop = self._property_map.get("source", "source_file")
            
            # Build Weaviate v4 query with near_vector using actual property names
            response = self.collection.query.near_vector(
                near_vector=embedding.tolist(),
                certainty=settings.similarity_threshold,
                limit=top_k,
                return_metadata=["certainty"],
                return_properties=[question_prop, answer_prop, source_prop]
            )
        except Exception as exc:  # pragma: no cover - defensive
            # If query failed, try with old schema as fallback
            error_msg = str(exc).lower()
            if "no such prop" in error_msg or "property" in error_msg:
                logger.warning("vector_store.search.schema_mismatch", error=str(exc), trying="old_schema")
                try:
                    # Fallback to old schema property names
                    response = self.collection.query.near_vector(
                        near_vector=embedding.tolist(),
                        certainty=settings.similarity_threshold,
                        limit=top_k,
                        return_metadata=["certainty"],
                        return_properties=["input", "label", "source_file"]
                    )
                    # Update property map for this query
                    self._property_map = {"question": "input", "answer": "label", "source": "source_file"}
                    question_prop = "input"
                    answer_prop = "label"
                    source_prop = "source_file"
                except Exception as fallback_exc:
                    logger.exception("vector_store.search.fallback_failed", error=str(fallback_exc))
                    return []
            else:
                logger.exception("vector_store.search.error", error=str(exc))
                return []

        results = []
        # Use the property names that were successfully used in the query
        # (either from detection or from fallback)
        question_prop = self._property_map.get("question", "input")
        answer_prop = self._property_map.get("answer", "label")
        source_prop = self._property_map.get("source", "source_file")
        
        # Weaviate v4 returns a QueryReturn with an objects attribute
        for obj in response.objects:
            
            question = ""
            answer = ""
            source = ""
            
            if isinstance(obj.properties, dict):
                question = obj.properties.get(question_prop, "")
                answer = obj.properties.get(answer_prop, "")
                source = obj.properties.get(source_prop, "")
            else:
                # Try attribute access
                question = getattr(obj.properties, question_prop, "")
                answer = getattr(obj.properties, answer_prop, "")
                source = getattr(obj.properties, source_prop, "")
            
            # For old schema where answer might be a label (integer), convert to string
            if answer_prop == "label" and isinstance(answer, (int, float)):
                answer = str(answer)
            
            # Extract similarity - use certainty if available, otherwise distance (inverted), default to 0.0
            similarity = 0.0
            if obj.metadata:
                if hasattr(obj.metadata, 'certainty') and obj.metadata.certainty is not None:
                    similarity = float(obj.metadata.certainty)
                elif hasattr(obj.metadata, 'distance') and obj.metadata.distance is not None:
                    # Convert distance to similarity (distance is lower for more similar items)
                    # For normalized vectors, distance = 1 - certainty approximately
                    similarity = max(0.0, 1.0 - float(obj.metadata.distance))
            
            results.append({
                "document_id": str(obj.uuid),
                "question": question,
                "answer": answer,
                "source": source,
                "similarity": similarity,
            })
            
        return results

    def add_entry(self, question: str, answer: str, source: str = "kb") -> str:
        """Add a new entry to the vector store."""
        # Generate embedding
        text = question + "\n" + answer
        embedding = self.encoder.encode(text)
        embedding = embedding / np.linalg.norm(embedding)

        # Add to Weaviate
        result = self.collection.data.insert(
            properties={
                "question": question,
                "answer": answer,
                "source": source,
            },
            vector=embedding.tolist()
        )

        return result.uuid


_vector_store: VectorStore | None = None


class _NullVectorStore:
    """Fallback vector store used when Weaviate is unavailable at startup.
    Provides the minimal API consumed by the workflow.
    """

    def search(self, query: str, top_k: int | None = None) -> List[Dict[str, Any]]:  # type: ignore[override]
        return []

    def add_entry(self, question: str, answer: str, source: str = "kb") -> str:  # pragma: no cover
        logger.warning("vector_store.null.add_entry_ignored")
        return ""


def load_vector_store(force_reload: bool = False) -> VectorStore:
    """Lazy-load the Weaviate vector store."""
    global _vector_store
    if _vector_store is not None and not force_reload:
        return _vector_store

    if not settings.weaviate_url or not settings.weaviate_api_key:
        logger.warning("vector_store.config.missing", msg="Starting without KB; searches will return empty.")
        _vector_store = _NullVectorStore()  # type: ignore[assignment]
        return _vector_store  # type: ignore[return-value]

    logger.info("vector_store.load.start", url=settings.weaviate_url)

    # Use the v4 helper to connect to Weaviate Cloud. The older v3-style
    # `weaviate.Client(url=..., auth_client_secret=...)` constructor is not
    # supported by the installed weaviate client and raises a TypeError.
    # connect_to_weaviate_cloud will construct the correct ConnectionParams
    # for cloud deployments (http + grpc hosts) and return a connected client.
    # pass the API key string directly — the helper will parse it into the
    # proper AuthCredentials object. Accessing `weaviate.Auth` at module
    # level can raise AttributeError in some installs; passing a string is
    # supported and avoids that problem.
    try:
        # Set strict timeouts to fail fast if Weaviate is unreachable
        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=settings.weaviate_url,
            auth_credentials=settings.weaviate_api_key,
            skip_init_checks=True,
            additional_config=weaviate.classes.init.AdditionalConfig(
                timeout=weaviate.classes.init.Timeout(init=3, query=3, insert=5)
            )
        )

        encoder = SentenceTransformer(settings.embedding_model_name)
        _vector_store = VectorStore(client=client, encoder=encoder)
        logger.info("vector_store.load.success")
        return _vector_store
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "vector_store.load.failed_starting_without_kb",
            error=str(exc),
        )
        _vector_store = _NullVectorStore()  # type: ignore[assignment]
        return _vector_store  # type: ignore[return-value]


def save_feedback_to_queue(feedback_record: dict) -> None:
    """Append feedback to feedback database."""

    feedback_path = Path(settings.feedback_store_path)
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    if feedback_path.exists():
        data = json.loads(feedback_path.read_text(encoding="utf-8"))
    else:
        data = []
    data.append(feedback_record)
    feedback_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def queue_candidate_kb_entry(question: str, solution: str, source: str) -> None:
    """Save a candidate knowledge base entry for human approval."""

    queue_path = Path("backend/data/kb_candidate_queue.json")
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    if queue_path.exists():
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
    else:
        queue = []
    queue.append({"question": question, "answer": solution, "source": source})
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")


