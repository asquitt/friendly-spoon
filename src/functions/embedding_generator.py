"""
Embedding Generation Function.

This serverless function generates embeddings using local models,
saving 90%+ on embedding costs compared to OpenAI.

Cost Comparison (per 1M embeddings):
- OpenAI text-embedding-ada-002: ~$100
- Local all-MiniLM-L6-v2: ~$0 (just compute time)
- With 95% cache hit rate: Even cheaper!

This function:
1. Checks cache first (Redis)
2. Generates embedding if not cached (using local model)
3. Caches result for future use
4. Returns embedding + metrics
"""

import time
from typing import List, Optional
import torch
from sentence_transformers import SentenceTransformer

from ..shared.config import get_config
from ..shared.logger import get_logger, log_cost_metric
from ..shared.models import EmbeddingRequest, EmbeddingResponse
from ..storage.cache import CacheManager

log = get_logger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings using local models with intelligent caching.

    This class:
    - Loads a sentence transformer model once (reuse across requests)
    - Checks cache before generating (major cost saver!)
    - Batches requests for efficiency
    - Tracks metrics (latency, cache hit rate, cost savings)

    Example:
        >>> generator = EmbeddingGenerator()
        >>> embedding, metrics = generator.generate("What is machine learning?")
        >>> print(f"Dimension: {len(embedding)}")
        >>> print(f"Cache hit: {metrics['cache_hit']}")
        >>> print(f"Latency: {metrics['latency_ms']:.1f}ms")
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        cache: Optional[CacheManager] = None
    ):
        """
        Initialize embedding generator.

        Args:
            model_name: Sentence transformer model name
            cache: Cache manager (creates one if not provided)

        Note:
            Model is loaded once and reused for all requests.
            This is important for serverless environments!
        """
        config = get_config()

        self.model_name = model_name or config.embedding_model
        self.device = config.embedding_model_device
        self.cache = cache or CacheManager()

        # Load model (this takes a few seconds on first load)
        log.info("loading_embedding_model", model=self.model_name, device=self.device)
        start = time.time()

        self.model = SentenceTransformer(self.model_name, device=self.device)

        load_time = (time.time() - start) * 1000
        log.info(
            "embedding_model_loaded",
            model=self.model_name,
            device=self.device,
            load_time_ms=load_time
        )

    def generate(
        self,
        text: str,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None
    ) -> tuple[List[float], dict]:
        """
        Generate embedding for text.

        Args:
            text: Input text
            use_cache: Whether to use caching
            cache_ttl: Cache TTL in seconds (None = use default)

        Returns:
            tuple: (embedding, metrics)
                - embedding: List of floats
                - metrics: Dict with cache_hit, latency_ms, cost_saved_usd

        Example:
            >>> embedding, metrics = generator.generate("Hello world")
            >>> print(f"Generated {len(embedding)}-dimensional embedding")
            >>> print(f"Cache hit: {metrics['cache_hit']}")
        """
        start_time = time.time()

        # Check cache first
        cache_hit = False
        if use_cache:
            cached_embedding = self.cache.get_embedding(text, model=self.model_name)

            if cached_embedding is not None:
                latency_ms = (time.time() - start_time) * 1000
                cache_hit = True

                log.debug(
                    "embedding_cache_hit",
                    text_length=len(text),
                    latency_ms=latency_ms
                )

                # Calculate cost saved (compared to OpenAI)
                cost_saved_usd = 0.0001  # Approximate OpenAI cost

                metrics = {
                    "cache_hit": True,
                    "latency_ms": latency_ms,
                    "cost_saved_usd": cost_saved_usd,
                    "model": self.model_name,
                }

                # Log cost metric
                log_cost_metric(
                    log,
                    operation="embedding",
                    model=self.model_name,
                    input_tokens=len(text.split()),
                    output_tokens=0,
                    cost_usd=0.0,  # Free from cache!
                    latency_ms=latency_ms,
                    cache_hit=True
                )

                return cached_embedding, metrics

        # Generate embedding
        log.debug("generating_embedding", text_length=len(text), model=self.model_name)

        with torch.no_grad():
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False
            )

        # Convert to list for JSON serialization
        embedding_list = embedding.tolist()

        # Cache result
        if use_cache:
            self.cache.set_embedding(
                text,
                embedding_list,
                model=self.model_name,
                ttl=cache_ttl
            )

        latency_ms = (time.time() - start_time) * 1000

        metrics = {
            "cache_hit": False,
            "latency_ms": latency_ms,
            "cost_saved_usd": 0.0,  # Local model = free!
            "model": self.model_name,
            "dimension": len(embedding_list),
        }

        # Log cost metric
        log_cost_metric(
            log,
            operation="embedding",
            model=self.model_name,
            input_tokens=len(text.split()),
            output_tokens=0,
            cost_usd=0.0,  # Free!
            latency_ms=latency_ms,
            cache_hit=False
        )

        log.info(
            "embedding_generated",
            text_length=len(text),
            dimension=len(embedding_list),
            latency_ms=latency_ms
        )

        return embedding_list, metrics

    def generate_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
        cache_ttl: Optional[int] = None
    ) -> tuple[List[List[float]], dict]:
        """
        Generate embeddings for multiple texts (batch processing).

        Batching is much more efficient than processing one at a time!

        Args:
            texts: List of input texts
            use_cache: Whether to use caching
            cache_ttl: Cache TTL in seconds

        Returns:
            tuple: (embeddings, metrics)
                - embeddings: List of embedding lists
                - metrics: Aggregated metrics

        Example:
            >>> texts = ["Hello", "World", "Machine Learning"]
            >>> embeddings, metrics = generator.generate_batch(texts)
            >>> print(f"Generated {len(embeddings)} embeddings")
            >>> print(f"Cache hit rate: {metrics['cache_hit_rate']:.1%}")
        """
        start_time = time.time()

        embeddings = []
        cache_hits = 0
        cache_misses = []
        cache_miss_indices = []

        # Check cache for each text
        if use_cache:
            for i, text in enumerate(texts):
                cached = self.cache.get_embedding(text, model=self.model_name)

                if cached is not None:
                    embeddings.append(cached)
                    cache_hits += 1
                else:
                    embeddings.append(None)  # Placeholder
                    cache_misses.append(text)
                    cache_miss_indices.append(i)
        else:
            cache_misses = texts
            cache_miss_indices = list(range(len(texts)))
            embeddings = [None] * len(texts)

        # Generate embeddings for cache misses (batch)
        if cache_misses:
            log.debug(
                "generating_batch_embeddings",
                total=len(texts),
                cache_hits=cache_hits,
                cache_misses=len(cache_misses)
            )

            with torch.no_grad():
                new_embeddings = self.model.encode(
                    cache_misses,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                    batch_size=32
                )

            # Cache and store results
            for i, (text, embedding) in enumerate(zip(cache_misses, new_embeddings)):
                embedding_list = embedding.tolist()

                # Cache it
                if use_cache:
                    self.cache.set_embedding(
                        text,
                        embedding_list,
                        model=self.model_name,
                        ttl=cache_ttl
                    )

                # Store in results
                embeddings[cache_miss_indices[i]] = embedding_list

        latency_ms = (time.time() - start_time) * 1000

        cache_hit_rate = cache_hits / len(texts) if texts else 0.0

        metrics = {
            "total_requests": len(texts),
            "cache_hits": cache_hits,
            "cache_misses": len(cache_misses),
            "cache_hit_rate": cache_hit_rate,
            "latency_ms": latency_ms,
            "avg_latency_per_text": latency_ms / len(texts) if texts else 0,
            "model": self.model_name,
            # Estimated cost savings
            "cost_saved_usd": cache_hits * 0.0001,  # OpenAI cost per embedding
        }

        log.info(
            "batch_embeddings_generated",
            total=len(texts),
            cache_hit_rate=cache_hit_rate,
            latency_ms=latency_ms
        )

        return embeddings, metrics

    def handle_request(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        Handle an embedding request (OpenFaaS handler format).

        Args:
            request: EmbeddingRequest object

        Returns:
            EmbeddingResponse: Response with embedding and metrics

        Example:
            >>> request = EmbeddingRequest(
            ...     request_id="req_123",
            ...     text="What is AI?",
            ... )
            >>> response = generator.handle_request(request)
            >>> print(f"Embedding dimension: {response.dimension}")
        """
        embedding, metrics = self.generate(
            request.text,
            use_cache=True,
            cache_ttl=request.cache_ttl
        )

        response = EmbeddingResponse(
            request_id=request.request_id,
            embedding=embedding,
            model=self.model_name,
            cache_hit=metrics["cache_hit"],
            latency_ms=metrics["latency_ms"],
            cost_usd=0.0,  # Local model is free!
        )

        return response


# =============================================================================
# OpenFaaS Handler (for serverless deployment)
# =============================================================================

# Global instance (loaded once, reused across requests)
_generator: Optional[EmbeddingGenerator] = None


def get_generator() -> EmbeddingGenerator:
    """Get or create global embedding generator."""
    global _generator

    if _generator is None:
        _generator = EmbeddingGenerator()

    return _generator


def handle(request_json: dict) -> dict:
    """
    OpenFaaS function handler.

    This is called by OpenFaaS for each request.

    Args:
        request_json: Request data (matches EmbeddingRequest schema)

    Returns:
        dict: Response data (matches EmbeddingResponse schema)

    Example request:
        {
            "request_id": "req_123",
            "text": "What is machine learning?",
            "model": "all-MiniLM-L6-v2"
        }
    """
    try:
        # Parse request
        request = EmbeddingRequest(**request_json)

        # Generate embedding
        generator = get_generator()
        response = generator.handle_request(request)

        # Return response
        return response.model_dump()

    except Exception as e:
        log.error("embedding_request_failed", error=str(e))
        return {
            "error": str(e),
            "request_id": request_json.get("request_id", "unknown")
        }


# =============================================================================
# Example Usage / Testing
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger

    setup_logger("embedding-generator", environment="local", debug=True)

    print("🤖 Initializing embedding generator...")
    generator = EmbeddingGenerator()

    # Single embedding
    print("\n📝 Generating single embedding...")
    text = "What is machine learning?"
    embedding, metrics = generator.generate(text)

    print(f"✅ Generated {len(embedding)}-dimensional embedding")
    print(f"   Latency: {metrics['latency_ms']:.1f}ms")
    print(f"   Cache hit: {metrics['cache_hit']}")

    # Second request (should hit cache)
    print("\n📝 Requesting same embedding again...")
    embedding2, metrics2 = generator.generate(text)

    print(f"✅ Retrieved from cache")
    print(f"   Latency: {metrics2['latency_ms']:.1f}ms (much faster!)")
    print(f"   Cache hit: {metrics2['cache_hit']}")
    print(f"   Cost saved: ${metrics2['cost_saved_usd']:.4f}")

    # Batch generation
    print("\n📝 Generating batch embeddings...")
    texts = [
        "Machine learning is great",
        "Deep learning uses neural networks",
        "Natural language processing",
        "What is machine learning?",  # This one is cached!
    ]

    embeddings, metrics = generator.generate_batch(texts)

    print(f"✅ Generated {len(embeddings)} embeddings")
    print(f"   Total latency: {metrics['latency_ms']:.1f}ms")
    print(f"   Avg latency: {metrics['avg_latency_per_text']:.1f}ms/text")
    print(f"   Cache hit rate: {metrics['cache_hit_rate']:.1%}")
    print(f"   Cost saved: ${metrics['cost_saved_usd']:.4f}")

    print("\n💰 Cost Analysis:")
    print("   Without caching: $0.0004 (4 embeddings × $0.0001)")
    print(f"   With caching: ${(4 - metrics['cache_hits']) * 0.0001:.4f}")
    print(f"   Savings: ${metrics['cost_saved_usd']:.4f}")
    print(f"   Savings rate: {metrics['cache_hit_rate']:.1%}")

    print("\n✅ Embedding generator test complete!")
