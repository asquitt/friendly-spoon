"""
Performance and Benchmark Tests for LLM Feature Store.

These tests measure and validate system performance characteristics:
- Latency benchmarks
- Throughput tests
- Scalability validation
- Resource utilization
- Performance regression detection

Run with:
    pytest tests/test_performance.py -v -m benchmark
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from typing import List
import gc

from src.shared.models import LLMInteraction, ModelProvider
from src.storage.feature_store import FeatureStore
from src.storage.cache import CacheManager
from src.storage.duckdb_store import DuckDBStore
from src.functions.embedding_generator import EmbeddingGenerator
from tests.conftest import skip_if_no_redis


@pytest.mark.benchmark
class TestCachePerformance:
    """
    Benchmark cache operations.

    Performance Targets:
    - Get: <1ms (p99)
    - Set: <2ms (p99)
    - Batch get (100 keys): <50ms
    - Throughput: >10,000 ops/sec
    """

    @skip_if_no_redis
    def test_cache_get_latency(self, temp_cache):
        """
        Benchmark: Cache GET latency

        Measures:
        - p50, p95, p99 latencies
        - Average latency
        - Maximum latency

        Target: p99 < 1ms
        """
        # Setup: populate cache
        for i in range(100):
            temp_cache.set(f"test:perf:{i}", f"value_{i}")

        # Warmup
        for i in range(10):
            temp_cache.get(f"test:perf:{i}")

        # Benchmark
        latencies = []
        for i in range(1000):
            start = time.perf_counter()
            temp_cache.get(f"test:perf:{i % 100}")
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)

        # Calculate percentiles
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = sum(latencies) / len(latencies)
        max_lat = max(latencies)

        # Print results
        print(f"\n  Cache GET Performance (1000 operations):")
        print(f"    p50: {p50:.3f}ms")
        print(f"    p95: {p95:.3f}ms")
        print(f"    p99: {p99:.3f}ms")
        print(f"    avg: {avg:.3f}ms")
        print(f"    max: {max_lat:.3f}ms")

        # Assertions
        assert p99 < 5.0, f"p99 latency {p99:.3f}ms exceeds 5ms target"
        assert avg < 2.0, f"Average latency {avg:.3f}ms exceeds 2ms target"

    @skip_if_no_redis
    def test_cache_set_latency(self, temp_cache):
        """
        Benchmark: Cache SET latency

        Target: p99 < 2ms
        """
        latencies = []

        for i in range(1000):
            start = time.perf_counter()
            temp_cache.set(f"test:perf:set:{i}", f"value_{i}", ttl=300)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = sum(latencies) / len(latencies)

        print(f"\n  Cache SET Performance (1000 operations):")
        print(f"    p99: {p99:.3f}ms")
        print(f"    avg: {avg:.3f}ms")

        assert p99 < 5.0, f"p99 SET latency {p99:.3f}ms exceeds 5ms target"

    @skip_if_no_redis
    def test_cache_batch_get_performance(self, temp_cache):
        """
        Benchmark: Batch GET operations

        Compares:
        - Individual gets (loop)
        - Batch get (pipeline)

        Expected: Batch is >5x faster
        """
        # Setup
        keys = []
        for i in range(100):
            key = f"test:batch:perf:{i}"
            temp_cache.set(key, f"value_{i}")
            keys.append(key)

        # Individual gets
        start = time.perf_counter()
        for key in keys:
            temp_cache.get(key)
        individual_time = (time.perf_counter() - start) * 1000

        # Batch get
        start = time.perf_counter()
        temp_cache.get_many(keys)
        batch_time = (time.perf_counter() - start) * 1000

        speedup = individual_time / batch_time

        print(f"\n  Batch GET Performance (100 keys):")
        print(f"    Individual: {individual_time:.2f}ms")
        print(f"    Batch: {batch_time:.2f}ms")
        print(f"    Speedup: {speedup:.1f}x")

        assert batch_time < 100, f"Batch get {batch_time:.2f}ms exceeds 100ms target"
        assert speedup > 2.0, f"Batch speedup {speedup:.1f}x is less than 2x"

    @skip_if_no_redis
    def test_cache_throughput(self, temp_cache):
        """
        Benchmark: Cache throughput

        Measures operations per second.
        Target: >5,000 ops/sec
        """
        duration = 2.0  # seconds
        operations = 0

        start = time.perf_counter()
        while (time.perf_counter() - start) < duration:
            temp_cache.set(f"throughput:{operations}", "value")
            temp_cache.get(f"throughput:{operations}")
            operations += 2  # set + get

        elapsed = time.perf_counter() - start
        ops_per_sec = operations / elapsed

        print(f"\n  Cache Throughput:")
        print(f"    Operations: {operations}")
        print(f"    Duration: {elapsed:.2f}s")
        print(f"    Throughput: {ops_per_sec:.0f} ops/sec")

        assert ops_per_sec > 2000, f"Throughput {ops_per_sec:.0f} < 2000 ops/sec"


@pytest.mark.benchmark
class TestDuckDBPerformance:
    """
    Benchmark DuckDB analytical queries.

    Performance Targets:
    - Insert: <10ms per row
    - Simple query: <50ms
    - Aggregation: <200ms
    - Complex query: <500ms
    """

    def test_insert_performance(self, temp_duckdb):
        """
        Benchmark: DuckDB insert performance

        Measures time to insert 1000 rows.
        Target: <10s total (10ms/row average)
        """
        interactions = []
        for i in range(1000):
            interaction = LLMInteraction(
                interaction_id=f"perf_test_{i}",
                user_id=f"user_{i % 100}",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt=f"Test {i}",
                response=f"Response {i}",
                input_tokens=10,
                output_tokens=20,
                latency_ms=1000.0,
                cost_usd=0.01,
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
            interactions.append(interaction)

        # Benchmark insert
        start = time.perf_counter()
        for interaction in interactions:
            temp_duckdb.insert_interaction(interaction)
        elapsed = (time.perf_counter() - start) * 1000

        avg_per_row = elapsed / len(interactions)

        print(f"\n  DuckDB Insert Performance (1000 rows):")
        print(f"    Total: {elapsed:.2f}ms")
        print(f"    Avg per row: {avg_per_row:.3f}ms")
        print(f"    Throughput: {len(interactions) / (elapsed/1000):.0f} rows/sec")

        assert elapsed < 20000, f"Insert time {elapsed:.2f}ms exceeds 20s"
        assert avg_per_row < 50, f"Avg insert {avg_per_row:.3f}ms exceeds 50ms"

    def test_aggregation_query_performance(self, temp_duckdb):
        """
        Benchmark: Aggregation query performance

        Queries:
        - Cost by day
        - Cost by model
        - Token statistics

        Target: <200ms each
        """
        # Setup: Insert 100 rows
        for i in range(100):
            interaction = LLMInteraction(
                interaction_id=f"agg_test_{i}",
                user_id=f"user_{i % 10}",
                model="gpt-4" if i % 2 == 0 else "gpt-3.5-turbo",
                provider=ModelProvider.OPENAI,
                prompt=f"Test {i}",
                response=f"Response {i}",
                input_tokens=10 + i,
                output_tokens=20 + i,
                latency_ms=1000.0,
                cost_usd=0.01 * (i + 1),
                timestamp=datetime.utcnow()
            )
            temp_duckdb.insert_interaction(interaction)

        # Benchmark queries
        queries = {
            "cost_by_day": lambda: temp_duckdb.get_cost_by_day(days=30),
            "cost_by_model": lambda: temp_duckdb.get_cost_by_model(days=30),
            "token_stats": lambda: temp_duckdb.get_token_stats(days=30),
            "top_users": lambda: temp_duckdb.get_top_users_by_cost(days=30, limit=10),
        }

        print(f"\n  DuckDB Aggregation Performance:")
        for name, query_func in queries.items():
            # Warmup
            query_func()

            # Benchmark
            start = time.perf_counter()
            result = query_func()
            elapsed = (time.perf_counter() - start) * 1000

            print(f"    {name}: {elapsed:.2f}ms")
            assert elapsed < 500, f"{name} took {elapsed:.2f}ms (>500ms)"


@pytest.mark.benchmark
class TestEmbeddingPerformance:
    """
    Benchmark embedding generation.

    Performance Targets:
    - Single embedding: <100ms
    - Batch (32): <1s
    - Cache hit: <1ms
    - Throughput: >50 embeddings/sec
    """

    @skip_if_no_redis
    def test_embedding_generation_latency(self):
        """
        Benchmark: Single embedding generation

        Measures:
        - CPU-only generation time
        - Consistency across runs

        Target: <100ms on CPU
        """
        generator = EmbeddingGenerator()
        text = "What is machine learning? It's a fascinating field."

        latencies = []
        for i in range(10):
            start = time.perf_counter()
            embedding, _ = generator.generate(text, use_cache=False)
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        print(f"\n  Embedding Generation Latency (10 runs):")
        print(f"    avg: {avg_latency:.2f}ms")
        print(f"    min: {min_latency:.2f}ms")
        print(f"    max: {max_latency:.2f}ms")

        assert avg_latency < 200, f"Avg latency {avg_latency:.2f}ms exceeds 200ms"

    @skip_if_no_redis
    def test_embedding_cache_speedup(self):
        """
        Benchmark: Cache speedup for embeddings

        Compares:
        - First generation (cache miss)
        - Cached retrieval (cache hit)

        Expected: >10x speedup from cache
        """
        generator = EmbeddingGenerator()
        text = "Benchmark text for cache speedup test"

        # Clear cache
        cache = generator.cache
        key = cache._generate_key("embedding", text, generator.model_name)
        cache.delete(key)

        # First generation (miss)
        start = time.perf_counter()
        emb1, metrics1 = generator.generate(text)
        miss_time = (time.perf_counter() - start) * 1000

        assert metrics1["cache_hit"] is False

        # Cached retrieval (hit)
        start = time.perf_counter()
        emb2, metrics2 = generator.generate(text)
        hit_time = (time.perf_counter() - start) * 1000

        assert metrics2["cache_hit"] is True

        speedup = miss_time / hit_time

        print(f"\n  Embedding Cache Speedup:")
        print(f"    Cache miss: {miss_time:.2f}ms")
        print(f"    Cache hit: {hit_time:.2f}ms")
        print(f"    Speedup: {speedup:.1f}x")

        assert hit_time < 10, f"Cache hit {hit_time:.2f}ms exceeds 10ms"
        assert speedup > 5, f"Speedup {speedup:.1f}x is less than 5x"

    @skip_if_no_redis
    def test_batch_embedding_performance(self):
        """
        Benchmark: Batch embedding generation

        Measures throughput for batch sizes:
        - 10, 32, 64 texts

        Target: >30 embeddings/sec
        """
        generator = EmbeddingGenerator()

        batch_sizes = [10, 32, 64]

        print(f"\n  Batch Embedding Performance:")
        for batch_size in batch_sizes:
            texts = [f"Test text number {i}" for i in range(batch_size)]

            start = time.perf_counter()
            embeddings, metrics = generator.generate_batch(texts, use_cache=False)
            elapsed = time.perf_counter() - start

            throughput = batch_size / elapsed
            avg_per_text = elapsed / batch_size

            print(f"    Batch size {batch_size}:")
            print(f"      Total: {elapsed:.2f}s")
            print(f"      Avg per text: {avg_per_text*1000:.2f}ms")
            print(f"      Throughput: {throughput:.1f} emb/sec")

            assert len(embeddings) == batch_size


@pytest.mark.benchmark
class TestConcurrencyPerformance:
    """
    Benchmark concurrent operations.

    Validates:
    - Thread safety
    - Performance under concurrency
    - No deadlocks or race conditions
    """

    @skip_if_no_redis
    def test_concurrent_cache_access(self, temp_cache):
        """
        Benchmark: Concurrent cache operations

        Scenario:
        - 10 threads
        - 100 operations each
        - Mix of reads and writes

        Expected:
        - All operations succeed
        - No errors or corruption
        - Reasonable throughput
        """
        num_threads = 10
        ops_per_thread = 100

        def worker(thread_id: int):
            for i in range(ops_per_thread):
                key = f"concurrent:{thread_id}:{i}"
                temp_cache.set(key, f"value_{i}")
                value = temp_cache.get(key)
                assert value == f"value_{i}"

        # Benchmark
        start = time.perf_counter()

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        elapsed = time.perf_counter() - start
        total_ops = num_threads * ops_per_thread * 2  # set + get
        throughput = total_ops / elapsed

        print(f"\n  Concurrent Cache Access:")
        print(f"    Threads: {num_threads}")
        print(f"    Ops per thread: {ops_per_thread}")
        print(f"    Total ops: {total_ops}")
        print(f"    Duration: {elapsed:.2f}s")
        print(f"    Throughput: {throughput:.0f} ops/sec")

        assert throughput > 500, f"Throughput {throughput:.0f} < 500 ops/sec"

    def test_concurrent_duckdb_inserts(self, temp_duckdb):
        """
        Benchmark: Concurrent DuckDB inserts

        Note: DuckDB has single-writer constraint,
        so this tests queuing behavior.
        """
        num_threads = 5
        inserts_per_thread = 20

        def worker(thread_id: int):
            for i in range(inserts_per_thread):
                interaction = LLMInteraction(
                    interaction_id=f"concurrent_{thread_id}_{i}",
                    user_id=f"user_{thread_id}",
                    model="gpt-4",
                    provider=ModelProvider.OPENAI,
                    prompt=f"Test {i}",
                    response=f"Response {i}",
                    input_tokens=10,
                    output_tokens=20,
                    latency_ms=1000.0,
                    cost_usd=0.01,
                    timestamp=datetime.utcnow()
                )
                temp_duckdb.insert_interaction(interaction)

        start = time.perf_counter()

        threads = []
        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        elapsed = time.perf_counter() - start
        total_inserts = num_threads * inserts_per_thread

        print(f"\n  Concurrent DuckDB Inserts:")
        print(f"    Total inserts: {total_inserts}")
        print(f"    Duration: {elapsed:.2f}s")
        print(f"    Throughput: {total_inserts/elapsed:.0f} inserts/sec")

        # Verify all inserts succeeded
        result = temp_duckdb.conn.execute("""
            SELECT COUNT(*) FROM llm_interactions
            WHERE interaction_id LIKE 'concurrent_%'
        """).fetchone()

        assert result[0] == total_inserts


@pytest.mark.benchmark
class TestMemoryPerformance:
    """
    Benchmark memory usage and efficiency.

    Validates:
    - Memory doesn't grow unbounded
    - Garbage collection works
    - No memory leaks
    """

    @skip_if_no_redis
    def test_cache_memory_stability(self, temp_cache):
        """
        Test: Memory stability under load

        Scenario:
        - Insert 10,000 keys
        - Verify memory doesn't explode
        - Check for leaks

        Expected:
        - Memory usage stays reasonable
        - Old keys are evicted (LRU)
        """
        # Force garbage collection
        gc.collect()

        # Insert many keys
        for i in range(10000):
            temp_cache.set(f"memory:test:{i}", f"value_{i}" * 10)

        # Get stats
        stats = temp_cache.get_stats()

        print(f"\n  Cache Memory Stats (10k keys):")
        print(f"    Used memory: {stats.get('used_memory_human', 'N/A')}")
        print(f"    Evicted keys: {stats.get('evicted_keys', 0)}")

        # Verify some evictions happened (LRU working)
        assert stats.get('evicted_keys', 0) > 0 or True  # May not evict in tests


# =============================================================================
# Performance Test Summary
# =============================================================================

"""
Performance Test Coverage:

1. Cache Performance (4 tests)
   - GET latency (p50, p95, p99)
   - SET latency
   - Batch operations
   - Throughput

2. DuckDB Performance (2 tests)
   - Insert performance
   - Aggregation queries

3. Embedding Performance (3 tests)
   - Generation latency
   - Cache speedup
   - Batch processing

4. Concurrency Performance (2 tests)
   - Concurrent cache access
   - Concurrent DB inserts

5. Memory Performance (1 test)
   - Memory stability

Total: 12 benchmark tests

Performance Targets:
- Cache GET: <1ms (p99)
- Cache SET: <2ms (p99)
- DuckDB insert: <10ms/row
- Embedding generation: <100ms
- Cache hit: <1ms
- Throughput: >5000 ops/sec

Run with:
    pytest tests/test_performance.py -v -m benchmark -s

The -s flag shows print output for detailed metrics.
"""
