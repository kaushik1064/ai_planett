"""Script to build FAISS vector store from knowledge base dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

from app.config import settings


def load_dataset(path: Path) -> list[dict]:
    data: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            data.append(json.loads(line))
    return data


def build_index(records: list[dict]) -> tuple[faiss.Index, np.ndarray]:
    encoder = SentenceTransformer(settings.embedding_model_name)
    corpus = [record["question"] + "\n" + record.get("answer", "") for record in records]
    embeddings = encoder.encode(corpus, show_progress_bar=True)
    embeddings = np.array(embeddings).astype("float32")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    return index, embeddings


def main(dataset_path: Path, output_index: Path, output_metadata: Path) -> None:
    records = load_dataset(dataset_path)
    index, _ = build_index(records)

    output_index.parent.mkdir(parents=True, exist_ok=True)
    output_metadata.parent.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(output_index))

    metadata = pd.DataFrame(records)
    metadata.to_parquet(output_metadata, index=False)

    print(f"Vector store written to {output_index}")
    print(f"Metadata written to {output_metadata}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build FAISS vector store for math agent")
    parser.add_argument("--dataset", type=Path, default=Path("backend/data/knowledge_base.jsonl"))
    parser.add_argument("--index", type=Path, default=Path(settings.vector_store_path))
    parser.add_argument("--metadata", type=Path, default=Path(settings.vector_store_metadata_path))
    args = parser.parse_args()

    main(args.dataset, args.index, args.metadata)


