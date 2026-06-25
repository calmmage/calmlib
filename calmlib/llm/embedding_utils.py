import hashlib
import json
from collections.abc import Sequence
from enum import Enum
from functools import lru_cache
from typing import Protocol

import numpy as np
from loguru import logger

try:
    from calmlib.logging import setup_logger_simple

    setup_logger_simple()
except Exception:  # pragma: no cover - logging should not fail the module import
    pass

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from pymongo.errors import PyMongoError
except ImportError:  # pragma: no cover - optional dependency
    MongoClient = None  # type: ignore[assignment]
    Collection = None  # type: ignore[assignment]
    PyMongoError = Exception  # type: ignore[assignment,misc]


class EmbeddingOption(str, Enum):
    OPENAI_API = "openai_api"
    GOOGLE_VTX_API = "google_vtx_api"
    AWS_BEDROCK_API = "aws_bedrock_api"
    COHERE_API = "cohere_api"
    LOCAL_SENTTRANSFORMERS = "local_sentence_transformers"
    LOCAL_OPEN_SOURCE = "local_open_source"
    HYBRID_ONPREM_API = "hybrid_onprem_api"


EMBEDDING_DEFAULTS: dict[EmbeddingOption, dict[str, str | bool]] = {
    EmbeddingOption.OPENAI_API: {
        "model": "text-embedding-3-large",
        "online": True,
    },
    EmbeddingOption.GOOGLE_VTX_API: {
        "model": "text-embedding-004",
        "online": True,
    },
    EmbeddingOption.AWS_BEDROCK_API: {
        "model": "amazon.titan-embed-text-v2:0",
        "online": True,
    },
    EmbeddingOption.COHERE_API: {
        "model": "embed-multilingual-v3.0",
        "online": True,
    },
    EmbeddingOption.LOCAL_SENTTRANSFORMERS: {
        "model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "online": False,
    },
    EmbeddingOption.LOCAL_OPEN_SOURCE: {
        "model": "BAAI/bge-m3",
        "online": False,
    },
    EmbeddingOption.HYBRID_ONPREM_API: {
        "model": "nomic-embed-text",
        "online": False,
    },
}

DEFAULT_ONLINE_OPTION = EmbeddingOption.OPENAI_API
# Flip to True to re-enable local embedding paths (sentence-transformers,
# bge-m3, ollama). Default offline option below still routes to OpenAI even
# when the flag is on — set it explicitly to a LOCAL_* option if you want
# offline-by-default again. See memory: feedback_block_local_models.
LOCAL_EMBEDDINGS_ENABLED = False
DEFAULT_OFFLINE_OPTION = EmbeddingOption.OPENAI_API

_LOCAL_OPTIONS: frozenset[EmbeddingOption] = frozenset(
    {
        EmbeddingOption.LOCAL_SENTTRANSFORMERS,
        EmbeddingOption.LOCAL_OPEN_SOURCE,
        EmbeddingOption.HYBRID_ONPREM_API,
    }
)


def _assert_local_embeddings_enabled(option: EmbeddingOption) -> None:
    if LOCAL_EMBEDDINGS_ENABLED:
        return
    raise RuntimeError(
        f"calmlib embedding option {option.value!r} is disabled "
        "(LOCAL_EMBEDDINGS_ENABLED=False in calmlib/llm/embedding_utils.py) — "
        "local sentence-transformers / bge-m3 / ollama paths cause laptop "
        "overheating. Switch this caller to EmbeddingOption.OPENAI_API or "
        "flip the flag to re-enable. See memory: feedback_block_local_models."
    )


class _MongoCache:
    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        db_name: str = "calmmage_embeddings",
        collection_name: str = "embedding_cache",
    ) -> None:
        self._collection: Collection | None = None
        if MongoClient is None:
            logger.debug("pymongo not installed, disabling MongoDB cache")
            return
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            collection = client[db_name][collection_name]
            collection.create_index("model", name="model_idx", background=True)
            collection.create_index("option", name="option_idx", background=True)
            self._collection = collection
        except Exception as exc:  # pragma: no cover - best effort cache
            logger.debug(f"MongoDB cache disabled ({exc})")
            self._collection = None

    def get_many(self, keys: Sequence[str]) -> dict[str, list[float]]:
        if not keys or self._collection is None:
            return {}
        try:
            cursor = self._collection.find({"_id": {"$in": list(keys)}})
            return {doc["_id"]: list(doc["embedding"]) for doc in cursor}
        except PyMongoError as exc:  # pragma: no cover - best effort cache
            logger.debug(f"MongoDB cache read failed: {exc}")
            return {}

    def set_many(
        self,
        items: dict[str, list[float]],
        *,
        model: str,
        option: EmbeddingOption,
    ) -> None:
        if not items or self._collection is None:
            return
        documents = [
            {
                "_id": key,
                "embedding": list(vector),
                "model": model,
                "option": option.value,
            }
            for key, vector in items.items()
        ]
        try:
            for doc in documents:
                self._collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": doc},
                    upsert=True,
                )
        except PyMongoError as exc:  # pragma: no cover - best effort cache
            logger.debug(f"MongoDB cache write failed: {exc}")


@lru_cache(maxsize=1)
def _mongo_cache() -> _MongoCache:
    from calmlib.utils import find_env_key

    uri = find_env_key("EMBEDDINGS_MONGO_URI", default="mongodb://localhost:27017")
    db_name = find_env_key("EMBEDDINGS_MONGO_DB", default="calmmage_embeddings")
    collection = find_env_key("EMBEDDINGS_MONGO_COLLECTION", default="embedding_cache")
    return _MongoCache(uri=uri, db_name=db_name, collection_name=collection)


def _cache_key(text: str, model: str, option: EmbeddingOption) -> str:
    key_source = f"{option.value}::{model}::{text}"
    return hashlib.sha256(key_source.encode("utf-8")).hexdigest()


def get_embeddings(
    texts: str | Sequence[str],
    *,
    allow_online: bool = True,
    specific_option: EmbeddingOption | None = None,
    specific_model: str | None = None,
    force_refresh: bool = False,
) -> list[list[float]]:
    if isinstance(texts, str):
        target_texts: list[str] = [texts]
        single_input = True
    else:
        target_texts = list(texts)
        single_input = False

    if not target_texts:
        return []

    option = specific_option
    if option is None:
        option = DEFAULT_ONLINE_OPTION if allow_online else DEFAULT_OFFLINE_OPTION

    if option in _LOCAL_OPTIONS:
        _assert_local_embeddings_enabled(option)

    option_defaults = EMBEDDING_DEFAULTS.get(option)
    if option_defaults is None:
        raise ValueError(f"Unsupported embedding option {option}")

    model_name = specific_model or str(option_defaults["model"])

    cache = _mongo_cache()
    cache_keys = [_cache_key(text, model_name, option) for text in target_texts]
    cached: dict[str, list[float]] = {}
    if not force_refresh:
        cached = cache.get_many(cache_keys)

    missing_indices: list[int] = []
    missing_texts: list[str] = []
    for idx, key in enumerate(cache_keys):
        if key not in cached:
            missing_indices.append(idx)
            missing_texts.append(target_texts[idx])

    new_embeddings: dict[str, list[float]] = {}
    if missing_texts:
        handler = _HANDLERS.get(option)
        if handler is None:
            raise ValueError(f"No handler registered for option {option}")
        try:
            computed = handler(missing_texts, model=model_name)
        except Exception as exc:
            logger.warning(f"{option.value} embedding failed: {exc}")
            auto_selected_online = (
                allow_online
                and option != DEFAULT_OFFLINE_OPTION
                and specific_option is None
            )
            if auto_selected_online:
                logger.info("Falling back to offline embedding option")
                return get_embeddings(
                    target_texts,
                    allow_online=False,
                    specific_option=None,
                    specific_model=None,
                    force_refresh=force_refresh,
                )
            raise

        if len(computed) != len(missing_texts):
            raise ValueError(
                f"{option.value} handler returned {len(computed)} embeddings for "
                f"{len(missing_texts)} texts",
            )

        for idx, vector in enumerate(computed):
            normalized = _normalize_vector(vector)
            cache_key = cache_keys[missing_indices[idx]]
            new_embeddings[cache_key] = normalized

        cache.set_many(new_embeddings, model=model_name, option=option)

    ordered_vectors = []
    for key in cache_keys:
        if key in cached and not force_refresh:
            ordered_vectors.append(_normalize_vector(cached[key]))
        else:
            ordered_vectors.append(_normalize_vector(new_embeddings[key]))

    if single_input:
        return [ordered_vectors[0]]
    return ordered_vectors


def cosine_similarity(vec1: Sequence[float], vec2: Sequence[float]) -> float:
    arr1 = np.asarray(vec1, dtype=np.float64)
    arr2 = np.asarray(vec2, dtype=np.float64)
    denominator = np.linalg.norm(arr1) * np.linalg.norm(arr2)
    if denominator == 0.0:
        return 0.0
    return float(np.clip(np.dot(arr1, arr2) / denominator, -1.0, 1.0))


def build_pairwise_similarity(
    labels: Sequence[str],
    embeddings: Sequence[Sequence[float]],
) -> list[tuple[str, str, float]]:
    if len(labels) != len(embeddings):
        raise ValueError("Labels and embeddings must have the same length")

    results: list[tuple[str, str, float]] = []
    for idx in range(len(labels)):
        for jdx in range(idx + 1, len(labels)):
            similarity = cosine_similarity(embeddings[idx], embeddings[jdx])
            results.append((labels[idx], labels[jdx], similarity))
    return results


def _normalize_vector(vector: Sequence[float] | np.ndarray) -> list[float]:
    if isinstance(vector, np.ndarray):
        return vector.astype(np.float32).tolist()
    return [float(value) for value in vector]


def _get_embeddings_openai_api(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    from calmlib.utils import find_env_key

    api_key = find_env_key("OPENAI_API_KEY") or find_env_key("CALMMAGE_OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY or CALMMAGE_OPENAI_API_KEY is required")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("Install openai package to use OpenAI embeddings") from exc

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model=model,
        input=list(texts),
    )
    return [item.embedding for item in response.data]


def _get_embeddings_cohere_api(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    from calmlib.utils import find_env_key

    api_key = find_env_key("COHERE_API_KEY") or find_env_key("CALMMAGE_COHERE_API_KEY")
    if not api_key:
        raise ValueError("COHERE_API_KEY or CALMMAGE_COHERE_API_KEY is required")

    try:
        import cohere
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("Install cohere package to use Cohere embeddings") from exc

    client = cohere.Client(api_key)
    response = client.embed(
        texts=list(texts),
        model=model,
    )
    return [list(vector) for vector in response.embeddings]


def _get_embeddings_google_vtx_api(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    from calmlib.utils import find_env_key

    api_key = find_env_key("GOOGLE_API_KEY") or find_env_key("CALMMAGE_GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY or CALMMAGE_GOOGLE_API_KEY is required")

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Install httpx package to use Google Vertex embeddings"
        ) from exc

    model_id = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_id}:batchEmbedContents"
    payload = {
        "requests": [
            {
                "model": model_id,
                "content": {"parts": [{"text": text}]},
            }
            for text in texts
        ]
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, params={"key": api_key}, json=payload)
        response.raise_for_status()
        data = response.json()
    embeddings = data.get("embeddings", [])
    if len(embeddings) != len(texts):
        raise ValueError(
            f"Google Vertex API returned {len(embeddings)} embeddings "
            f"for {len(texts)} texts",
        )
    return [list(item.get("values", [])) for item in embeddings]


def _get_embeddings_aws_bedrock_api(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError("Install boto3 to use AWS Bedrock embeddings") from exc

    from calmlib.utils import find_env_key

    region = find_env_key("BEDROCK_REGION") or find_env_key("AWS_REGION") or "us-east-1"
    client = boto3.client("bedrock-runtime", region_name=region)
    embeddings: list[list[float]] = []
    for text in texts:
        body = json.dumps({"inputText": text})
        response = client.invoke_model(modelId=model, body=body)
        payload = json.loads(response["body"].read())
        embeddings.append(list(payload["embedding"]))
    return embeddings


@lru_cache(maxsize=4)
def _load_sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Install sentence-transformers to use local embedding models",
        ) from exc

    return SentenceTransformer(model_name)


def _get_embeddings_local_sentence_transformers(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    _assert_local_embeddings_enabled(EmbeddingOption.LOCAL_SENTTRANSFORMERS)
    # Prefer the long-lived embed server — loading bge-m3 costs ~3–5 s per
    # Python process, and a CLI like `pb find` would pay that on every run.
    from calmlib.llm.embed_server import client as embed_client

    if embed_client.is_alive():
        try:
            return embed_client.embed_remote(list(texts), model=model)
        except Exception as exc:
            logger.warning(f"embed server call failed, falling back in-process: {exc}")

    sentence_model = _load_sentence_transformer(model)
    vectors = sentence_model.encode(
        list(texts),
        convert_to_numpy=True,
        normalize_embeddings=False,
    )
    return [vec.astype(np.float32).tolist() for vec in vectors]


def _get_embeddings_local_open_source(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    _assert_local_embeddings_enabled(EmbeddingOption.LOCAL_OPEN_SOURCE)
    # Reuse sentence-transformers loader for open-source models (e.g., BGE, E5).
    return _get_embeddings_local_sentence_transformers(texts, model=model)


def _get_embeddings_hybrid_onprem_api(
    texts: Sequence[str],
    *,
    model: str,
) -> list[list[float]]:
    _assert_local_embeddings_enabled(EmbeddingOption.HYBRID_ONPREM_API)
    from calmlib.utils import find_env_key

    try:
        import httpx
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Install httpx to call hybrid/on-prem embedding endpoints"
        ) from exc

    base_url = find_env_key("OLLAMA_BASE_URL", default="http://localhost:11434")
    endpoint = f"{base_url.rstrip('/')}/api/embeddings"
    client_timeout = float(find_env_key("OLLAMA_TIMEOUT", default="60"))

    embeddings: list[list[float]] = []
    with httpx.Client(timeout=client_timeout) as http_client:
        for text in texts:
            payload = {"model": model, "prompt": text}
            response = http_client.post(endpoint, json=payload)
            response.raise_for_status()
            data = response.json()
            vector = data.get("embedding")
            if vector is None:
                raise ValueError("Hybrid embedding endpoint returned no embedding")
            embeddings.append(list(vector))
    return embeddings


class _EmbeddingHandler(Protocol):
    def __call__(self, texts: Sequence[str], *, model: str) -> list[list[float]]: ...


_HANDLERS: dict[EmbeddingOption, _EmbeddingHandler] = {
    EmbeddingOption.OPENAI_API: _get_embeddings_openai_api,
    EmbeddingOption.GOOGLE_VTX_API: _get_embeddings_google_vtx_api,
    EmbeddingOption.AWS_BEDROCK_API: _get_embeddings_aws_bedrock_api,
    EmbeddingOption.COHERE_API: _get_embeddings_cohere_api,
    EmbeddingOption.LOCAL_SENTTRANSFORMERS: _get_embeddings_local_sentence_transformers,
    EmbeddingOption.LOCAL_OPEN_SOURCE: _get_embeddings_local_open_source,
    EmbeddingOption.HYBRID_ONPREM_API: _get_embeddings_hybrid_onprem_api,
}
