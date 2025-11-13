"""
Regression Tests for LLM Feature Store.

These tests ensure that:
1. Existing functionality continues to work
2. API contracts are maintained
3. Performance doesn't degrade
4. Data formats remain compatible

Purpose:
- Catch breaking changes before they reach production
- Validate backwards compatibility
- Ensure stable API contracts
- Detect performance regressions

Run with:
    pytest tests/test_regression.py -v
"""

import pytest
import json
from datetime import datetime, timedelta
from typing import Dict, Any

from src.shared.models import (
    LLMInteraction,
    ModelProvider,
    Feature,
    FeatureType,
    EmbeddingRequest,
    EmbeddingResponse,
    DriftDetectionResult,
    DriftStatus,
    CostSummary
)
from src.shared.config import get_config, get_cost_estimate
from src.storage.feature_store import FeatureStore
from tests.conftest import skip_if_no_redis


class TestAPIContractRegression:
    """
    Test that API contracts remain stable.

    Validates:
    - Model schemas don't change unexpectedly
    - Required fields remain required
    - Optional fields remain optional
    - Serialization format is stable
    """

    def test_llm_interaction_schema_stability(self):
        """
        Regression Test: LLMInteraction schema must remain stable

        This ensures that existing code depending on this model
        continues to work across versions.

        Critical fields that MUST exist:
        - interaction_id, user_id, model, provider
        - prompt, response
        - input_tokens, output_tokens
        - latency_ms, cost_usd
        - timestamp
        """
        # Create interaction with all expected fields
        interaction = LLMInteraction(
            interaction_id="regression_test_001",
            user_id="test_user",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt="Test prompt",
            response="Test response",
            input_tokens=10,
            output_tokens=20,
            latency_ms=1000.0,
            cost_usd=0.01,
            timestamp=datetime.utcnow()
        )

        # Verify all critical fields exist
        assert hasattr(interaction, 'interaction_id')
        assert hasattr(interaction, 'user_id')
        assert hasattr(interaction, 'model')
        assert hasattr(interaction, 'provider')
        assert hasattr(interaction, 'prompt')
        assert hasattr(interaction, 'response')
        assert hasattr(interaction, 'input_tokens')
        assert hasattr(interaction, 'output_tokens')
        assert hasattr(interaction, 'latency_ms')
        assert hasattr(interaction, 'cost_usd')
        assert hasattr(interaction, 'timestamp')

        # Verify computed properties exist
        assert hasattr(interaction, 'total_tokens')
        assert hasattr(interaction, 'cost_per_token')

        # Verify values are correct types
        assert isinstance(interaction.interaction_id, str)
        assert isinstance(interaction.input_tokens, int)
        assert isinstance(interaction.output_tokens, int)
        assert isinstance(interaction.cost_usd, float)

    def test_llm_interaction_serialization_format(self):
        """
        Regression Test: Serialization format must be stable

        This ensures that serialized data can be deserialized
        across versions without breaking.
        """
        interaction = LLMInteraction(
            interaction_id="ser_test_001",
            user_id="test_user",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt="Test",
            response="Response",
            input_tokens=10,
            output_tokens=20,
            latency_ms=1000.0,
            cost_usd=0.01,
            timestamp=datetime.utcnow()
        )

        # Serialize to JSON
        json_str = interaction.model_dump_json()
        json_data = json.loads(json_str)

        # Verify expected keys exist
        expected_keys = {
            'interaction_id', 'user_id', 'model', 'provider',
            'prompt', 'response', 'input_tokens', 'output_tokens',
            'latency_ms', 'cost_usd', 'timestamp'
        }

        for key in expected_keys:
            assert key in json_data, f"Key '{key}' missing from serialized data"

        # Verify deserialization works
        reconstructed = LLMInteraction(**json_data)
        assert reconstructed.interaction_id == interaction.interaction_id
        assert reconstructed.cost_usd == interaction.cost_usd

    def test_feature_store_api_stability(self, temp_duckdb):
        """
        Regression Test: FeatureStore API must remain stable

        Critical methods that MUST exist:
        - write_interaction()
        - get_online_features()
        - get_offline_features()
        - get_cost_summary()
        """
        from src.storage.cache import CacheManager

        fs = FeatureStore(
            cache=CacheManager() if skip_if_no_redis.args[0] else None,
            duckdb=temp_duckdb,
            delta=None
        )

        # Verify critical methods exist
        assert hasattr(fs, 'write_interaction')
        assert hasattr(fs, 'get_online_features')
        assert hasattr(fs, 'get_offline_features')
        assert hasattr(fs, 'get_cost_summary')

        # Verify they're callable
        assert callable(fs.write_interaction)
        assert callable(fs.get_online_features)
        assert callable(fs.get_offline_features)
        assert callable(fs.get_cost_summary)


class TestDataFormatRegression:
    """
    Test that data formats remain compatible.

    Ensures:
    - Database schemas are backwards compatible
    - Cache key formats are stable
    - Configuration formats are stable
    """

    def test_duckdb_schema_stability(self, temp_duckdb):
        """
        Regression Test: DuckDB schema must be stable

        Verifies that required columns exist in:
        - llm_interactions table
        - features table
        """
        # Check llm_interactions table
        result = temp_duckdb.conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'llm_interactions'
        """).fetchall()

        columns = [row[0] for row in result]

        required_columns = {
            'interaction_id', 'user_id', 'model', 'provider',
            'prompt', 'response', 'input_tokens', 'output_tokens',
            'total_tokens', 'latency_ms', 'cost_usd', 'timestamp', 'date'
        }

        for col in required_columns:
            assert col in columns, f"Required column '{col}' missing from llm_interactions"

        # Check features table
        result = temp_duckdb.conn.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'features'
        """).fetchall()

        columns = [row[0] for row in result]

        required_columns = {
            'feature_name', 'entity_id', 'value', 'feature_type',
            'timestamp', 'date', 'version'
        }

        for col in required_columns:
            assert col in columns, f"Required column '{col}' missing from features"

    def test_config_format_stability(self):
        """
        Regression Test: Configuration format must be stable

        Verifies that critical config values exist and are correct type.
        """
        config = get_config()

        # Critical config values that must exist
        assert hasattr(config, 'environment')
        assert hasattr(config, 'kafka_bootstrap_servers')
        assert hasattr(config, 'redis_host')
        assert hasattr(config, 'redis_port')
        assert hasattr(config, 'embedding_model')
        assert hasattr(config, 'embedding_cache_ttl')

        # Verify types
        assert isinstance(config.redis_port, int)
        assert isinstance(config.embedding_cache_ttl, int)
        assert isinstance(config.kafka_bootstrap_servers, str)

    def test_cache_key_format_stability(self, temp_cache):
        """
        Regression Test: Cache key format must be stable

        This ensures that cached data from previous versions
        can still be retrieved.
        """
        # Test embedding cache key format
        text = "test text"
        model = "test-model"

        # Store with known format
        temp_cache.set_embedding(text, [0.1, 0.2], model=model)

        # Retrieve should work
        cached = temp_cache.get_embedding(text, model=model)
        assert cached is not None

        # Test feature cache key format
        temp_cache.set_feature("entity_123", "feature_name", 42.0)
        cached = temp_cache.get_feature("entity_123", "feature_name")
        assert cached == 42.0


class TestPerformanceRegression:
    """
    Test that performance doesn't degrade.

    Ensures:
    - Operations stay within expected latency bounds
    - Throughput doesn't decrease
    - Memory usage doesn't grow
    """

    @skip_if_no_redis
    def test_cache_latency_regression(self, temp_cache):
        """
        Regression Test: Cache latency must stay below threshold

        Baseline: p99 < 5ms for GET operations

        If this test fails, it indicates a performance regression
        in the cache layer.
        """
        import time

        # Setup
        for i in range(100):
            temp_cache.set(f"perf:reg:{i}", f"value_{i}")

        # Measure
        latencies = []
        for i in range(100):
            start = time.perf_counter()
            temp_cache.get(f"perf:reg:{i}")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)

        latencies.sort()
        p99 = latencies[int(len(latencies) * 0.99)]

        # Baseline threshold
        MAX_P99_MS = 10.0  # Conservative threshold

        assert p99 < MAX_P99_MS, \
            f"Performance regression: p99 latency {p99:.3f}ms exceeds baseline {MAX_P99_MS}ms"

    def test_duckdb_insert_performance_regression(self, temp_duckdb):
        """
        Regression Test: DuckDB insert performance

        Baseline: Average insert < 50ms per row

        If this test fails, check for:
        - Added indexes slowing down inserts
        - Schema changes
        - Lock contention
        """
        import time

        interactions = []
        for i in range(100):
            interaction = LLMInteraction(
                interaction_id=f"perf_reg_{i}",
                user_id="test_user",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt="Test",
                response="Response",
                input_tokens=10,
                output_tokens=20,
                latency_ms=1000.0,
                cost_usd=0.01,
                timestamp=datetime.utcnow()
            )
            interactions.append(interaction)

        start = time.perf_counter()
        for interaction in interactions:
            temp_duckdb.insert_interaction(interaction)
        elapsed = (time.perf_counter() - start) * 1000

        avg_per_row = elapsed / len(interactions)

        # Baseline threshold
        MAX_AVG_MS = 100.0  # Conservative

        assert avg_per_row < MAX_AVG_MS, \
            f"Performance regression: avg insert {avg_per_row:.2f}ms exceeds baseline {MAX_AVG_MS}ms"


class TestBackwardsCompatibility:
    """
    Test backwards compatibility of data and APIs.

    Ensures:
    - Old data formats can still be read
    - API changes are backwards compatible
    - Migrations work correctly
    """

    def test_old_interaction_format_compatibility(self):
        """
        Regression Test: Old interaction data format must still work

        Simulates data from an older version to ensure it can
        still be loaded.
        """
        # Simulate old format (before metadata field was added)
        old_data = {
            "interaction_id": "old_format_001",
            "user_id": "test_user",
            "model": "gpt-4",
            "provider": "openai",
            "prompt": "Old prompt",
            "response": "Old response",
            "input_tokens": 10,
            "output_tokens": 20,
            "latency_ms": 1000.0,
            "cost_usd": 0.01,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Should be able to load old format
        try:
            interaction = LLMInteraction(**old_data)
            assert interaction.interaction_id == "old_format_001"
            assert interaction.metadata == {}  # Default value
        except Exception as e:
            pytest.fail(f"Failed to load old format: {e}")

    def test_optional_fields_remain_optional(self):
        """
        Regression Test: Optional fields must remain optional

        This prevents breaking changes where optional fields
        become required.
        """
        # These fields should be optional
        interaction = LLMInteraction(
            interaction_id="optional_test",
            user_id="test_user",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt="Test",
            response="Response",
            input_tokens=10,
            output_tokens=20,
            latency_ms=1000.0,
            cost_usd=0.01
            # Note: session_id, metadata not provided (optional)
        )

        assert interaction.session_id is None
        assert interaction.metadata == {}


class TestCostCalculationRegression:
    """
    Test that cost calculations remain accurate.

    Ensures:
    - Cost formulas are correct
    - Pricing doesn't accidentally change
    - Aggregations are accurate
    """

    def test_cost_estimate_accuracy(self):
        """
        Regression Test: Cost estimates must be accurate

        This ensures pricing hasn't accidentally changed.
        """
        # Known pricing (as of test creation)
        # These values are documented in config.py
        gpt4_cost = get_cost_estimate("gpt-4", 100, 50)
        gpt35_cost = get_cost_estimate("gpt-3.5-turbo", 100, 50)

        # Calculate expected values
        # GPT-4: $0.03 per 1K input, $0.06 per 1K output
        expected_gpt4 = (100/1000 * 0.03) + (50/1000 * 0.06)

        # GPT-3.5: $0.0015 per 1K input, $0.002 per 1K output
        expected_gpt35 = (100/1000 * 0.0015) + (50/1000 * 0.002)

        assert abs(gpt4_cost - expected_gpt4) < 0.0001, \
            f"GPT-4 cost changed: expected {expected_gpt4}, got {gpt4_cost}"

        assert abs(gpt35_cost - expected_gpt35) < 0.0001, \
            f"GPT-3.5 cost changed: expected {expected_gpt35}, got {gpt35_cost}"

    def test_total_tokens_calculation(self):
        """
        Regression Test: Total tokens = input + output

        This formula MUST NOT change.
        """
        interaction = LLMInteraction(
            interaction_id="tokens_test",
            user_id="test_user",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt="Test",
            response="Response",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1000.0,
            cost_usd=0.01,
            timestamp=datetime.utcnow()
        )

        assert interaction.total_tokens == 150
        assert interaction.total_tokens == interaction.input_tokens + interaction.output_tokens


# =============================================================================
# Regression Test Summary
# =============================================================================

"""
Regression Test Coverage:

1. API Contract Stability (3 tests)
   - Model schemas unchanged
   - Serialization format stable
   - FeatureStore API stable

2. Data Format Stability (3 tests)
   - Database schemas unchanged
   - Configuration format stable
   - Cache key format stable

3. Performance Baselines (2 tests)
   - Cache latency within bounds
   - DuckDB insert within bounds

4. Backwards Compatibility (2 tests)
   - Old data formats work
   - Optional fields remain optional

5. Cost Calculation (2 tests)
   - Cost estimates accurate
   - Token calculations correct

Total: 12 regression tests

These tests act as a safety net to catch:
- Breaking API changes
- Schema changes
- Performance degradation
- Pricing changes
- Formula changes

Run with:
    pytest tests/test_regression.py -v

These tests should NEVER fail unless:
1. You intentionally made a breaking change
2. You updated the test to reflect new behavior
3. There's a bug that needs fixing

If a regression test fails unexpectedly, investigate immediately!
"""
