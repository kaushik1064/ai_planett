"""Script to build Weaviate vector store from knowledge base dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import weaviate
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from app.config import settings


def load_dataset(path: Path) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            data.append(json.loads(line))
    return data


def get_weaviate_client() -> weaviate.Client:
    """Initialize Weaviate client with authentication."""
    auth_config = weaviate.auth.AuthApiKey(api_key=settings.weaviate_api_key)
    client = weaviate.Client(
        url=settings.weaviate_url,
        auth_client_secret=auth_config,
    )
    return client


def setup_schema(client: weaviate.Client) -> None:
    """Create the schema if it doesn't exist."""
    if not client.schema.exists(settings.weaviate_class_name):
        class_obj = {
            "class": settings.weaviate_class_name,
            "vectorizer": "none",  # We'll provide our own vectors
            "properties": [
                {"name": "question", "dataType": ["text"]},
                {"name": "answer", "dataType": ["text"]},
                {"name": "source", "dataType": ["text"]},
            ]
        }
        client.schema.create_class(class_obj)


def build_index(client: weaviate.Client, records: List[Dict[str, Any]], batch_size: int = 100) -> None:
    """Build the vector index by importing records in batches."""
    encoder = SentenceTransformer(settings.embedding_model_name)
    
    with client.batch as batch:
        batch.batch_size = batch_size
        
        for record in tqdm(records, desc="Importing records"):
            # Generate embedding from question and answer
            text = record["question"] + "\n" + record.get("answer", "")
            embedding = encoder.encode(text)
            
            # Normalize the embedding
            embedding = embedding / np.linalg.norm(embedding)
            
            # Prepare properties
            properties = {
                "question": record["question"],
                "answer": record.get("answer", ""),
                "source": record.get("source", "")
            }
            
            # Import the object with its vector
            batch.add_data_object(
                data_object=properties,
                class_name=settings.weaviate_class_name,
                vector=embedding.tolist()
            )


def main(dataset_path: Path) -> None:
    print(f"Loading dataset from {dataset_path}")
    records = load_dataset(dataset_path)
    
    print("Initializing Weaviate client")
    client = get_weaviate_client()
    
    print("Setting up schema")
    setup_schema(client)
    
    print("Building index")
    build_index(client, records)
    
    print(f"Successfully imported {len(records)} records to Weaviate")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Weaviate vector store for math agent")
    parser.add_argument("--dataset", type=Path, default=Path("backend/data/knowledge_base.jsonl"))
    args = parser.parse_args()

    main(args.dataset)