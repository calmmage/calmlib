"""Embeddings utilities for semantic search and similarity.

Legacy wrapper around embedding_utils.py for backwards compatibility.
"""

from calmlib.llm.embedding_utils import (
    cosine_similarity as _cosine_similarity,
    get_embeddings as _get_embeddings,
)


def get_embedding(
    text: str,
    model: str = "text-embedding-3-small",
) -> list[float]:
    """
    Get embedding vector for text using OpenAI with disk caching.

    Args:
        text: Text to embed
        model: Embedding model to use

    Returns:
        Embedding vector as list of floats
    """
    # Delegate to embedding_utils.get_embeddings
    result = _get_embeddings(
        text,
        allow_online=True,
        specific_model=model,
    )
    return result[0]


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    # Delegate to embedding_utils.cosine_similarity
    return _cosine_similarity(vec1, vec2)


def batch_get_embeddings(
    texts: list[str],
    model: str = "text-embedding-3-small",
) -> list[list[float]]:
    """
    Get embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed
        model: Embedding model to use

    Returns:
        List of embedding vectors
    """
    # Delegate to embedding_utils.get_embeddings
    return _get_embeddings(
        texts,
        allow_online=True,
        specific_model=model,
    )


def find_most_similar(
    query: str,
    candidates: list[str],
    model: str = "text-embedding-3-small",
    top_k: int = 5,
) -> list[tuple[int, float, str]]:
    """
    Find most similar texts to a query.

    Args:
        query: Query text
        candidates: List of candidate texts
        model: Embedding model to use
        top_k: Number of top results to return

    Returns:
        List of (index, similarity_score, text) tuples
    """
    # Get embeddings using embedding_utils
    query_emb = get_embedding(query, model=model)
    candidate_embs = batch_get_embeddings(candidates, model=model)

    # Calculate similarities
    similarities = [
        (idx, cosine_similarity(query_emb, cand_emb), text)
        for idx, (cand_emb, text) in enumerate(zip(candidate_embs, candidates))
    ]

    # Sort by similarity (highest first) and return top_k
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:top_k]
