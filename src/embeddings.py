"""
Embedding service supporting both local transformers and OpenAI API.
Handles caching, batching, and device management.
"""
from __future__ import annotations
import hashlib
import redis
import json
from typing import List
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)

# Lazy imports to avoid loading heavy dependencies at module level
_embedding_model = None
_openai_client = None
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client

def _get_local_model():
    """Lazy load sentence transformers model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        import torch
        
        device = settings.embedding_device
        if device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, falling back to CPU")
            device = "cpu"
        
        logger.info(f"Loading {settings.embedding_model} on {device}")
        _embedding_model = SentenceTransformer(settings.embedding_model, device=device)
    return _embedding_model


def _get_openai_client():
    """Lazy load OpenAI client."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def normalize_text(text: str) -> str:
    """Normalize text for consistent hashing and embedding."""
    return " ".join(text.strip().lower().split())

def get_embedding_dimension() -> int:
    """Return the embedding dimension for the configured model."""
    return settings.embedding_dimension

def compute_text_hash(text: str) -> str:
    """Compute a simple hash for the text for caching purposes."""
    normalized_text = normalize_text(text)
    return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

def generate_embedding(text: str) -> List[float]:
    """Generate embedding for a single text without caching."""
    if settings.embedding_provider == "local":
        model = _get_local_model()
        embedding = model.encode([text])[0].tolist()
    elif settings.embedding_provider == "openai":
        client = _get_openai_client()
        response = client.embeddings.create(
            input=text,
            model=settings.embedding_model
        )
        embedding = response.data[0].embedding
    else:
        raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
    return embedding

def get_embedding_from_cache(text: str) -> List[float]:
    """Get embedding for a single text, using cache if available."""
    import time
    start_time = time.perf_counter()
    
    text_hash = compute_text_hash(text)
    text_preview = text[:50] + "..." if len(text) > 50 else text
    redis_client = get_redis_client()
    
    cached: bytes | None = redis_client.get(text_hash)  # type: ignore[assignment]
    if cached is not None:
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"[CACHE HIT] Embedding retrieved from cache in {duration:.2f}ms | hash={text_hash[:12]}... | text='{text_preview}'")
        cached_str = cached.decode('utf-8') if isinstance(cached, bytes) else str(cached)
        return json.loads(cached_str)
    
    # Cache miss - generate new embedding
    gen_start = time.perf_counter()
    embedding = generate_embedding(text)
    gen_duration = (time.perf_counter() - gen_start) * 1000
    
    # Cache the embedding
    redis_client.set(text_hash, json.dumps(embedding))
    
    total_duration = (time.perf_counter() - start_time) * 1000
    logger.info(f"[CACHE MISS] Embedding generated in {gen_duration:.2f}ms, cached | hash={text_hash[:12]}... | text='{text_preview}' | total={total_duration:.2f}ms")
    return embedding

__all__ = [
    "get_embedding_from_cache",
    "get_embedding_dimension",
    "generate_embedding",
    "compute_text_hash",
    "normalize_text",
    "get_redis_client",
]
