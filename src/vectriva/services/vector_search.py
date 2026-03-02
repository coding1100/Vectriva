"""Vector search utilities with provider-agnostic support."""

import struct
from typing import Any

import numpy as np


def serialize_embedding(embedding: list[float]) -> bytes:
    """Serialize embedding to bytes for storage."""
    return struct.pack(f"{len(embedding)}f", *embedding)


def deserialize_embedding(data: bytes) -> list[float]:
    """Deserialize embedding from bytes."""
    n = len(data) // 4
    return list(struct.unpack(f"{n}f", data))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    arr_a = np.array(a)
    arr_b = np.array(b)
    return float(np.dot(arr_a, arr_b) / (np.linalg.norm(arr_a) * np.linalg.norm(arr_b)))


def find_top_k_similar(
    query_embedding: list[float],
    chunk_embeddings: list[tuple[str, bytes]],
    k: int = 5,
) -> list[tuple[str, float]]:
    """
    Find top-k most similar chunks to query.

    Args:
        query_embedding: Query vector
        chunk_embeddings: List of (chunk_id, embedding_bytes) tuples
        k: Number of results to return

    Returns:
        List of (chunk_id, similarity_score) tuples, sorted by score descending
    """
    similarities = []
    for chunk_id, embedding_bytes in chunk_embeddings:
        chunk_embedding = deserialize_embedding(embedding_bytes)
        similarity = cosine_similarity(query_embedding, chunk_embedding)
        similarities.append((chunk_id, similarity))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:k]
