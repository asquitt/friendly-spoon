"""
Pytest fixtures and configuration.

This module provides reusable test fixtures for:
- Mock databases
- Test data generators
- Configuration overrides
- Cleanup utilities
"""

import pytest
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Generator
import redis
import duckdb

from src.shared.models import LLMInteraction, ModelProvider, EmbeddingRequest
from src.shared.config import get_config
from src.storage.cache import CacheManager
from src.storage.duckdb_store import DuckDBStore
from src.storage.feature_store import FeatureStore


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def test_config():
    """
    Override configuration for testing.

    This ensures tests use isolated resources and don't affect
    production data.
    """
    import os
    os.environ['ENVIRONMENT'] = 'test'
    os.environ['DEBUG'] = 'true'
    os.environ['REDIS_DB'] = '15'  # Use separate Redis DB for tests

    config = get_config()
    return config


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def temp_duckdb() -> Generator[DuckDBStore, None, None]:
    """
    Create a temporary DuckDB database for testing.

    This fixture:
    1. Creates an in-memory DuckDB instance
    2. Initializes tables
    3. Yields the store for testing
    4. Cleans up automatically

    Example:
        >>> def test_something(temp_duckdb):
        ...     temp_duckdb.insert_interaction(interaction)
        ...     assert temp_duckdb.get_cost_by_day(days=1)
    """
    store = DuckDBStore(db_path=":memory:")
    yield store
    store.close()


@pytest.fixture
def temp_cache() -> Generator[CacheManager, None, None]:
    """
    Create a test Redis cache manager.

    Uses a separate Redis database (15) to avoid conflicts with
    development data.

    Automatically flushes the test DB after each test.
    """
    cache = CacheManager()

    # Clear test database before test
    cache.redis.flushdb()

    yield cache

    # Clean up after test
    cache.redis.flushdb()


@pytest.fixture
def temp_feature_store(
    temp_cache,
    temp_duckdb
) -> Generator[FeatureStore, None, None]:
    """
    Create a complete feature store with temporary storage.

    This provides an isolated feature store for integration testing.
    """
    # Skip Delta Lake for tests (would need MinIO setup)
    store = FeatureStore(
        cache=temp_cache,
        duckdb=temp_duckdb,
        delta=None
    )

    yield store


# =============================================================================
# Data Generation Fixtures
# =============================================================================

@pytest.fixture
def sample_interaction() -> LLMInteraction:
    """
    Generate a sample LLM interaction for testing.

    Returns:
        LLMInteraction: A valid interaction object with realistic data

    Example:
        >>> def test_interaction(sample_interaction):
        ...     assert sample_interaction.total_tokens > 0
    """
    return LLMInteraction(
        interaction_id="test_int_001",
        user_id="test_user_001",
        session_id="test_session_001",
        model="gpt-4",
        provider=ModelProvider.OPENAI,
        prompt="What is machine learning?",
        response="Machine learning is a subset of AI that enables systems to learn from data.",
        input_tokens=5,
        output_tokens=15,
        latency_ms=1250.5,
        cost_usd=0.0024,
        timestamp=datetime.utcnow()
    )


@pytest.fixture
def sample_interactions(sample_interaction) -> list[LLMInteraction]:
    """
    Generate multiple sample interactions for batch testing.

    Returns:
        list[LLMInteraction]: 10 interactions with varied data
    """
    interactions = []

    for i in range(10):
        interaction = LLMInteraction(
            interaction_id=f"test_int_{i:03d}",
            user_id=f"test_user_{i % 3:03d}",  # 3 different users
            session_id=f"test_session_{i // 3:03d}",
            model="gpt-4" if i % 2 == 0 else "gpt-3.5-turbo",
            provider=ModelProvider.OPENAI,
            prompt=f"Test prompt {i}",
            response=f"Test response {i}",
            input_tokens=10 + i,
            output_tokens=20 + i,
            latency_ms=1000.0 + (i * 100),
            cost_usd=0.001 * (i + 1),
            timestamp=datetime.utcnow() - timedelta(hours=i)
        )
        interactions.append(interaction)

    return interactions


@pytest.fixture
def sample_embedding_request() -> EmbeddingRequest:
    """
    Generate a sample embedding request for testing.

    Returns:
        EmbeddingRequest: A valid embedding request
    """
    return EmbeddingRequest(
        request_id="test_emb_req_001",
        text="What is machine learning?",
        model="all-MiniLM-L6-v2",
        entity_id="test_user_001",
        interaction_id="test_int_001"
    )


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_redis(monkeypatch):
    """
    Mock Redis for tests that don't need real Redis.

    This uses a dictionary to simulate Redis behavior.
    """
    storage = {}

    class MockRedis:
        def get(self, key):
            return storage.get(key)

        def setex(self, key, ttl, value):
            storage[key] = value
            return True

        def delete(self, key):
            if key in storage:
                del storage[key]
                return True
            return False

        def ping(self):
            return True

        def info(self, section=None):
            return {
                'keyspace_hits': 100,
                'keyspace_misses': 10,
                'connected_clients': 1,
            }

        def flushdb(self):
            storage.clear()

    return MockRedis()


# =============================================================================
# Benchmark Fixtures
# =============================================================================

@pytest.fixture
def benchmark_data():
    """
    Generate data for performance benchmarks.

    Returns:
        dict: Various sizes of test data
    """
    return {
        'small': 100,      # 100 interactions
        'medium': 1000,    # 1K interactions
        'large': 10000,    # 10K interactions
    }


# =============================================================================
# Cleanup Utilities
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """
    Automatically clean up temporary files after each test.

    This runs after every test to ensure no leftover files.
    """
    yield

    # Clean up any .duckdb files in tests directory
    import glob
    for db_file in glob.glob("tests/**/*.duckdb", recursive=True):
        try:
            import os
            os.remove(db_file)
        except:
            pass


# =============================================================================
# Logging Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def setup_test_logging():
    """
    Configure logging for tests.

    This ensures test output is readable and structured.
    """
    from src.shared.logger import setup_logger

    setup_logger(
        service_name="test",
        environment="test",
        debug=True
    )


# =============================================================================
# Markers
# =============================================================================

def pytest_configure(config):
    """
    Register custom pytest markers.

    Markers allow you to categorize and selectively run tests:
    - @pytest.mark.slow: Tests that take >1 second
    - @pytest.mark.integration: Integration tests requiring services
    - @pytest.mark.benchmark: Performance benchmarks
    - @pytest.mark.requires_redis: Tests that need Redis
    - @pytest.mark.requires_kafka: Tests that need Kafka
    """
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "benchmark: marks tests as performance benchmarks"
    )
    config.addinivalue_line(
        "markers", "requires_redis: marks tests that require Redis"
    )
    config.addinivalue_line(
        "markers", "requires_kafka: marks tests that require Kafka"
    )


# =============================================================================
# Utility Functions
# =============================================================================

def is_redis_available() -> bool:
    """
    Check if Redis is available for testing.

    Returns:
        bool: True if Redis is reachable
    """
    try:
        r = redis.Redis(host='localhost', port=6379, db=15)
        return r.ping()
    except:
        return False


def is_kafka_available() -> bool:
    """
    Check if Kafka is available for testing.

    Returns:
        bool: True if Kafka is reachable
    """
    try:
        from kafka import KafkaConsumer
        consumer = KafkaConsumer(
            bootstrap_servers=['localhost:9094'],
            request_timeout_ms=5000
        )
        consumer.close()
        return True
    except:
        return False


# Skip tests if services not available
skip_if_no_redis = pytest.mark.skipif(
    not is_redis_available(),
    reason="Redis not available"
)

skip_if_no_kafka = pytest.mark.skipif(
    not is_kafka_available(),
    reason="Kafka not available"
)
