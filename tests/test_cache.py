"""
Unit tests for cache manager.

Tests cover:
- Basic get/set operations
- Embedding caching
- Feature caching
- Batch operations
- Cache statistics
- Error handling
"""

import pytest
import pickle
from typing import List

from src.storage.cache import CacheManager
from tests.conftest import skip_if_no_redis


@skip_if_no_redis
class TestCacheManager:
    """Test cases for CacheManager."""

    def test_basic_set_and_get(self, temp_cache):
        """Test basic cache set and get operations."""
        key = "test:key"
        value = {"foo": "bar", "baz": 123}

        # Set value
        success = temp_cache.set(key, value, ttl=300)
        assert success is True

        # Get value
        retrieved = temp_cache.get(key)
        assert retrieved == value

    def test_get_nonexistent_key(self, temp_cache):
        """Test getting a key that doesn't exist."""
        result = temp_cache.get("nonexistent:key")
        assert result is None

    def test_cache_expiration(self, temp_cache):
        """Test that cached values expire based on TTL."""
        import time

        key = "test:expiring"
        value = "test_value"

        # Set with 1 second TTL
        temp_cache.set(key, value, ttl=1)

        # Should exist immediately
        assert temp_cache.get(key) == value

        # Wait for expiration
        time.sleep(1.1)

        # Should be gone
        assert temp_cache.get(key) is None

    def test_delete_key(self, temp_cache):
        """Test deleting a key from cache."""
        key = "test:delete"
        value = "test_value"

        # Set value
        temp_cache.set(key, value)
        assert temp_cache.get(key) == value

        # Delete
        deleted = temp_cache.delete(key)
        assert deleted is True

        # Should be gone
        assert temp_cache.get(key) is None

    def test_delete_nonexistent_key(self, temp_cache):
        """Test deleting a key that doesn't exist."""
        deleted = temp_cache.delete("nonexistent:key")
        assert deleted is False

    def test_embedding_caching(self, temp_cache):
        """Test caching embeddings."""
        text = "What is machine learning?"
        model = "all-MiniLM-L6-v2"
        embedding = [0.1, 0.2, 0.3] * 128  # 384 dimensions

        # Cache embedding
        success = temp_cache.set_embedding(text, embedding, model=model)
        assert success is True

        # Retrieve embedding
        cached_embedding = temp_cache.get_embedding(text, model=model)
        assert cached_embedding == embedding

    def test_embedding_cache_miss(self, temp_cache):
        """Test embedding cache miss."""
        embedding = temp_cache.get_embedding("unknown text", model="test-model")
        assert embedding is None

    def test_different_models_different_cache(self, temp_cache):
        """Test that different models have separate cache entries."""
        text = "Test text"
        embedding1 = [0.1] * 384
        embedding2 = [0.2] * 384

        # Cache with model 1
        temp_cache.set_embedding(text, embedding1, model="model-1")

        # Cache with model 2
        temp_cache.set_embedding(text, embedding2, model="model-2")

        # Should retrieve different embeddings
        cached1 = temp_cache.get_embedding(text, model="model-1")
        cached2 = temp_cache.get_embedding(text, model="model-2")

        assert cached1 == embedding1
        assert cached2 == embedding2
        assert cached1 != cached2

    def test_feature_caching(self, temp_cache):
        """Test caching feature values."""
        entity_id = "user_123"
        feature_name = "avg_tokens"
        value = 150.5

        # Cache feature
        success = temp_cache.set_feature(entity_id, feature_name, value)
        assert success is True

        # Retrieve feature
        cached_value = temp_cache.get_feature(entity_id, feature_name)
        assert cached_value == value

    def test_feature_cache_miss(self, temp_cache):
        """Test feature cache miss."""
        value = temp_cache.get_feature("unknown_user", "unknown_feature")
        assert value is None

    def test_batch_get(self, temp_cache):
        """Test batch retrieval of multiple keys."""
        # Set multiple keys
        keys = []
        for i in range(5):
            key = f"test:batch:{i}"
            temp_cache.set(key, f"value_{i}")
            keys.append(key)

        # Batch get
        values = temp_cache.get_many(keys)

        assert len(values) == 5
        for i, value in enumerate(values):
            assert value == f"value_{i}"

    def test_batch_get_with_misses(self, temp_cache):
        """Test batch get with some cache misses."""
        # Set some keys (not all)
        temp_cache.set("test:batch:0", "value_0")
        temp_cache.set("test:batch:2", "value_2")
        temp_cache.set("test:batch:4", "value_4")

        keys = [f"test:batch:{i}" for i in range(5)]
        values = temp_cache.get_many(keys)

        assert len(values) == 5
        assert values[0] == "value_0"
        assert values[1] is None  # Miss
        assert values[2] == "value_2"
        assert values[3] is None  # Miss
        assert values[4] == "value_4"

    def test_batch_get_empty_list(self, temp_cache):
        """Test batch get with empty list."""
        values = temp_cache.get_many([])
        assert values == []

    def test_clear_pattern(self, temp_cache):
        """Test clearing keys by pattern."""
        # Set multiple keys
        temp_cache.set("test:user:1:feature", "value1")
        temp_cache.set("test:user:2:feature", "value2")
        temp_cache.set("test:user:3:feature", "value3")
        temp_cache.set("other:key", "other")

        # Clear user keys
        deleted = temp_cache.clear_pattern("test:user:*")

        assert deleted == 3  # Should delete 3 keys

        # Verify they're gone
        assert temp_cache.get("test:user:1:feature") is None
        assert temp_cache.get("test:user:2:feature") is None
        assert temp_cache.get("test:user:3:feature") is None

        # Other key should still exist
        assert temp_cache.get("other:key") == "other"

    def test_cache_stats(self, temp_cache):
        """Test retrieving cache statistics."""
        # Perform some operations
        temp_cache.set("test:1", "value1")
        temp_cache.get("test:1")  # Hit
        temp_cache.get("nonexistent")  # Miss

        stats = temp_cache.get_stats()

        assert "hit_rate" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "total_requests" in stats
        assert isinstance(stats["hit_rate"], float)

    def test_health_check(self, temp_cache):
        """Test cache health check."""
        healthy = temp_cache.health_check()
        assert healthy is True

    def test_large_value_caching(self, temp_cache):
        """Test caching large values (like embeddings)."""
        # Create a large embedding (1536 dimensions like OpenAI)
        large_embedding = [0.1] * 1536

        success = temp_cache.set("test:large", large_embedding)
        assert success is True

        retrieved = temp_cache.get("test:large")
        assert retrieved == large_embedding
        assert len(retrieved) == 1536

    def test_complex_value_serialization(self, temp_cache):
        """Test caching complex Python objects."""
        complex_value = {
            "string": "test",
            "number": 123,
            "float": 45.67,
            "list": [1, 2, 3],
            "nested": {
                "a": 1,
                "b": [4, 5, 6]
            }
        }

        temp_cache.set("test:complex", complex_value)
        retrieved = temp_cache.get("test:complex")

        assert retrieved == complex_value
        assert isinstance(retrieved["nested"], dict)

    def test_concurrent_access(self, temp_cache):
        """Test concurrent cache access (thread safety)."""
        import threading

        results = []

        def worker(i):
            key = f"test:concurrent:{i}"
            temp_cache.set(key, f"value_{i}")
            value = temp_cache.get(key)
            results.append(value == f"value_{i}")

        # Create 10 threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All operations should succeed
        assert all(results)
        assert len(results) == 10


@skip_if_no_redis
class TestCacheErrorHandling:
    """Test cache error handling."""

    def test_graceful_failure_on_get(self, temp_cache, monkeypatch):
        """Test that get fails gracefully on Redis errors."""
        def mock_get_error(*args, **kwargs):
            from redis.exceptions import RedisError
            raise RedisError("Connection failed")

        monkeypatch.setattr(temp_cache.redis, "get", mock_get_error)

        # Should return None on error (not crash)
        result = temp_cache.get("test:key")
        assert result is None

    def test_graceful_failure_on_set(self, temp_cache, monkeypatch):
        """Test that set fails gracefully on Redis errors."""
        def mock_set_error(*args, **kwargs):
            from redis.exceptions import RedisError
            raise RedisError("Connection failed")

        monkeypatch.setattr(temp_cache.redis, "setex", mock_set_error)

        # Should return False on error (not crash)
        result = temp_cache.set("test:key", "value")
        assert result is False


@pytest.mark.benchmark
@skip_if_no_redis
class TestCachePerformance:
    """Performance benchmarks for cache operations."""

    def test_get_performance(self, temp_cache, benchmark_data):
        """Benchmark cache get operations."""
        import time

        # Set up test data
        for i in range(100):
            temp_cache.set(f"test:perf:{i}", f"value_{i}")

        # Benchmark gets
        start = time.time()
        for i in range(100):
            temp_cache.get(f"test:perf:{i}")
        elapsed = (time.time() - start) * 1000  # ms

        # Should be fast (< 100ms for 100 operations)
        assert elapsed < 100

        print(f"\n  Cache get (100 ops): {elapsed:.2f}ms")
        print(f"  Avg per operation: {elapsed/100:.2f}ms")

    def test_batch_get_performance(self, temp_cache):
        """Benchmark batch get operations."""
        import time

        # Set up test data
        keys = []
        for i in range(100):
            key = f"test:batch:perf:{i}"
            temp_cache.set(key, f"value_{i}")
            keys.append(key)

        # Benchmark batch get
        start = time.time()
        values = temp_cache.get_many(keys)
        elapsed = (time.time() - start) * 1000  # ms

        # Batch should be much faster than individual gets
        assert elapsed < 50  # Should be < 50ms

        print(f"\n  Batch get (100 keys): {elapsed:.2f}ms")
        print(f"  Avg per key: {elapsed/100:.2f}ms")
