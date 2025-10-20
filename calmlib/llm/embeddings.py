"""Embeddings utilities for semantic search and similarity."""

import hashlib
import json
from pathlib import Path

import numpy as np
from loguru import logger


def _get_cache_dir() -> Path:
    """Get embeddings cache directory."""
    cache_dir = Path.home() / ".cache" / "calmmage" / "embeddings"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cache_key(text: str, model: str) -> str:
    """Generate cache key from text and model."""
    content = f"{model}:{text}"
    return hashlib.sha256(content.encode()).hexdigest()


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
    # Check cache first
    cache_dir = _get_cache_dir()
    cache_key = _get_cache_key(text, model)
    cache_file = cache_dir / f"{cache_key}.json"

    if cache_file.exists():
        try:
            with open(cache_file) as f:
                cached_data = json.load(f)
                return cached_data["embedding"]
        except Exception as e:
            logger.debug(f"Cache read failed for {cache_key}: {e}")

    # Cache miss - fetch from API
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "OpenAI package not installed. Install with: pip install openai"
        )

    # Get API key from environment
    from calmlib.utils.env_discovery import find_env_key

    api_key = find_env_key("OPENAI_API_KEY")
    if not api_key:
        api_key = find_env_key("CALMMAGE_OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY or CALMMAGE_OPENAI_API_KEY not found")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(input=text, model=model)

    embedding = response.data[0].embedding

    # Save to cache
    try:
        with open(cache_file, "w") as f:
            json.dump(
                {"embedding": embedding, "model": model, "text_hash": cache_key}, f
            )
    except Exception as e:
        logger.debug(f"Cache write failed for {cache_key}: {e}")

    return embedding


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0.0 to 1.0)
    """
    arr1 = np.array(vec1)
    arr2 = np.array(vec2)

    # Calculate dot product and magnitudes
    dot_product = np.dot(arr1, arr2)
    magnitude1 = np.linalg.norm(arr1)
    magnitude2 = np.linalg.norm(arr2)

    # Avoid division by zero
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return float(dot_product / (magnitude1 * magnitude2))


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
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "OpenAI package not installed. Install with: pip install openai"
        )

    from calmlib.utils.env_discovery import find_env_key

    api_key = find_env_key("OPENAI_API_KEY")
    if not api_key:
        api_key = find_env_key("CALMMAGE_OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY or CALMMAGE_OPENAI_API_KEY not found")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(input=texts, model=model)

    return [item.embedding for item in response.data]


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
    # Get query embedding
    query_emb = get_embedding(query, model=model)

    # Get candidate embeddings
    candidate_embs = batch_get_embeddings(candidates, model=model)

    # Calculate similarities
    similarities = [
        (idx, cosine_similarity(query_emb, cand_emb), text)
        for idx, (cand_emb, text) in enumerate(zip(candidate_embs, candidates))
    ]

    # Sort by similarity (highest first) and return top_k
    similarities.sort(key=lambda x: x[1], reverse=True)

    return similarities[:top_k]
