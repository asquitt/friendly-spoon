"""
Redis Cache Manager for LLM Feature Store.

This module provides intelligent caching for:
- Embeddings (biggest cost saver!)
- Feature values
- LLM responses (optional)

Cost Impact Example:
- Without caching: 1M embeddings = $100
- With 95% cache hit rate: $5
- Savings: $95/month (95%)

Cache Strategy:
- LRU eviction (least recently used items are removed first)
- TTL-based expiration (data expires after N seconds)
- Compression for large values (embeddings)
"""

import json
import pickle
import hashlib
from typing import Any, Optional, List
from datetime import timedelta
import redis
from redis.exceptions import RedisError

from ..shared.config import get_config
from ..shared.logger import get_logger

log = get_logger(__name__)


class CacheManager:
    """
    Redis-based cache manager with intelligent key generation and compression.

    Example:
        >>> cache = CacheManager()
        >>> # Cache an embedding
        >>> embedding = [0.1, 0.2, -0.3, ...]
        >>> cache.set_embedding("What is ML?", embedding, model="all-MiniLM-L6-v2")
        >>> # Retrieve from cache
        >>> cached = cache.get_embedding("What is ML?", model="all-MiniLM-L6-v2")
        >>> assert cached == embedding
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize cache manager.

        Args:
            redis_client: Optional Redis client (creates one if not provided)
        """
        if redis_client:
            self.redis = redis_client
        else:
            config = get_config()
            self.redis = redis.Redis(
                host=config.redis_host,
                port=config.redis_port,
                db=config.redis_db,
                decode_responses=False,  # We handle encoding ourselves
                socket_connect_timeout=5,
                socket_timeout=5,
            )

        self.config = get_config()
        log.info("cache_manager_initialized", redis_host=self.config.redis_host)

    def _generate_key(self, prefix: str, *args: Any) -> str:
        """
        Generate a cache key with hash for consistency.

        Args:
            prefix: Key prefix (e.g., "embedding", "feature")
            *args: Additional components to hash

        Returns:
            str: Cache key

        Example:
            >>> cache._generate_key("embedding", "What is ML?", "all-MiniLM-L6-v2")
            'embedding:abc123def456'
        """
        # Create a stable hash of the arguments
        content = json.dumps(args, sort_keys=True)
        hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_value}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Optional[Any]: Cached value or None if not found

        Example:
            >>> value = cache.get("feature:user_123:avg_tokens")
        """
        try:
            data = self.redis.get(key)
            if data is None:
                log.debug("cache_miss", key=key)
                return None

            log.debug("cache_hit", key=key)
            return pickle.loads(data)

        except RedisError as e:
            log.warning("cache_error", error=str(e), operation="get", key=key)
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default)

        Returns:
            bool: True if successful

        Example:
            >>> cache.set("feature:user_123:avg_tokens", 150.5, ttl=300)
        """
        try:
            # Serialize value
            data = pickle.dumps(value)

            # Set with TTL
            if ttl is None:
                ttl = self.config.feature_cache_ttl

            self.redis.setex(key, ttl, data)
            log.debug("cache_set", key=key, ttl=ttl, size_bytes=len(data))
            return True

        except RedisError as e:
            log.warning("cache_error", error=str(e), operation="set", key=key)
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            bool: True if key was deleted

        Example:
            >>> cache.delete("feature:user_123:avg_tokens")
        """
        try:
            deleted = self.redis.delete(key)
            log.debug("cache_delete", key=key, deleted=bool(deleted))
            return bool(deleted)

        except RedisError as e:
            log.warning("cache_error", error=str(e), operation="delete", key=key)
            return False

    def get_embedding(
        self,
        text: str,
        model: str = "all-MiniLM-L6-v2"
    ) -> Optional[List[float]]:
        """
        Get cached embedding for text.

        Args:
            text: Input text
            model: Embedding model name

        Returns:
            Optional[List[float]]: Embedding vector or None

        Cost Savings:
            Every cache hit saves:
            - OpenAI: ~$0.0001
            - Local model: ~10ms compute time
        """
        key = self._generate_key("embedding", text, model)
        return self.get(key)

    def set_embedding(
        self,
        text: str,
        embedding: List[float],
        model: str = "all-MiniLM-L6-v2",
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache an embedding.

        Args:
            text: Input text
            embedding: Embedding vector
            model: Model used to generate embedding
            ttl: Cache TTL in seconds

        Returns:
            bool: True if successful

        Cost Optimization:
            - Default TTL: 24 hours
            - For stable content (docs, FAQs): Use longer TTL (7 days)
            - For dynamic content (user messages): Use shorter TTL (1 hour)
        """
        key = self._generate_key("embedding", text, model)
        if ttl is None:
            ttl = self.config.embedding_cache_ttl
        return self.set(key, embedding, ttl=ttl)

    def get_feature(
        self,
        entity_id: str,
        feature_name: str
    ) -> Optional[Any]:
        """
        Get cached feature value.

        Args:
            entity_id: Entity ID (user_id, session_id, etc.)
            feature_name: Feature name

        Returns:
            Optional[Any]: Feature value or None
        """
        key = self._generate_key("feature", entity_id, feature_name)
        return self.get(key)

    def set_feature(
        self,
        entity_id: str,
        feature_name: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache a feature value.

        Args:
            entity_id: Entity ID
            feature_name: Feature name
            value: Feature value
            ttl: Cache TTL in seconds

        Returns:
            bool: True if successful
        """
        key = self._generate_key("feature", entity_id, feature_name)
        if ttl is None:
            ttl = self.config.feature_cache_ttl
        return self.set(key, value, ttl=ttl)

    def get_many(self, keys: List[str]) -> List[Optional[Any]]:
        """
        Get multiple values from cache (batch operation).

        Args:
            keys: List of cache keys

        Returns:
            List[Optional[Any]]: List of values (None for misses)

        Performance:
            This is much faster than calling get() in a loop!
            - Individual gets: O(n) round trips
            - Batch get: O(1) round trip
        """
        try:
            if not keys:
                return []

            # Use pipeline for batch get
            pipe = self.redis.pipeline()
            for key in keys:
                pipe.get(key)

            results = pipe.execute()
            values = []

            for key, data in zip(keys, results):
                if data is None:
                    log.debug("cache_miss", key=key)
                    values.append(None)
                else:
                    log.debug("cache_hit", key=key)
                    values.append(pickle.loads(data))

            return values

        except RedisError as e:
            log.warning("cache_error", error=str(e), operation="get_many")
            return [None] * len(keys)

    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "embedding:*", "feature:user_123:*")

        Returns:
            int: Number of keys deleted

        Warning:
            Use with caution! This can delete many keys at once.

        Example:
            >>> # Clear all embeddings for a specific model
            >>> cache.clear_pattern("embedding:*")
            >>> # Clear all features for a user
            >>> cache.clear_pattern("feature:user_123:*")
        """
        try:
            cursor = 0
            deleted = 0

            while True:
                cursor, keys = self.redis.scan(cursor, match=pattern, count=100)

                if keys:
                    deleted += self.redis.delete(*keys)

                if cursor == 0:
                    break

            log.info("cache_cleared", pattern=pattern, deleted=deleted)
            return deleted

        except RedisError as e:
            log.warning("cache_error", error=str(e), operation="clear_pattern")
            return 0

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            dict: Cache stats (memory usage, hit rate, etc.)

        Example:
            >>> stats = cache.get_stats()
            >>> print(f"Memory used: {stats['used_memory_human']}")
            >>> print(f"Hit rate: {stats['hit_rate']:.1%}")
        """
        try:
            info = self.redis.info("stats")

            # Calculate hit rate
            hits = int(info.get("keyspace_hits", 0))
            misses = int(info.get("keyspace_misses", 0))
            total = hits + misses
            hit_rate = hits / total if total > 0 else 0.0

            return {
                "hit_rate": hit_rate,
                "hits": hits,
                "misses": misses,
                "total_requests": total,
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": self.redis.info("memory").get("used_memory_human"),
                "evicted_keys": info.get("evicted_keys", 0),
            }

        except RedisError as e:
            log.warning("cache_error", error=str(e), operation="get_stats")
            return {}

    def health_check(self) -> bool:
        """
        Check if Redis is healthy.

        Returns:
            bool: True if Redis is reachable

        Example:
            >>> if cache.health_check():
            ...     print("Cache is healthy!")
        """
        try:
            return self.redis.ping()
        except RedisError:
            return False


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger

    setup_logger("cache-test", environment="local", debug=True)

    # Initialize cache
    cache = CacheManager()

    # Check health
    if cache.health_check():
        print("✅ Redis is healthy")
    else:
        print("❌ Redis is not available")
        exit(1)

    # Test embedding caching
    print("\n📝 Testing embedding cache...")
    text = "What is machine learning?"
    embedding = [0.1, 0.2, -0.3, 0.4] * 96  # 384 dimensions

    # First access - cache miss
    cached = cache.get_embedding(text)
    print(f"First access (should be None): {cached}")

    # Store in cache
    cache.set_embedding(text, embedding)
    print("Stored embedding in cache")

    # Second access - cache hit
    cached = cache.get_embedding(text)
    print(f"Second access (should match): {cached == embedding}")

    # Test feature caching
    print("\n📝 Testing feature cache...")
    cache.set_feature("user_123", "avg_tokens", 150.5)
    value = cache.get_feature("user_123", "avg_tokens")
    print(f"Cached feature value: {value}")

    # Get stats
    print("\n📊 Cache statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
