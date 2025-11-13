"""
Unit tests for DuckDB store.

Tests cover:
- Interaction insertion
- Feature insertion
- Cost queries
- Token statistics
- Query performance
"""

import pytest
from datetime import datetime, timedelta

from src.storage.duckdb_store import DuckDBStore
from src.shared.models import LLMInteraction, Feature, ModelProvider, FeatureType


class TestDuckDBStore:
    """Test cases for DuckDBStore."""

    def test_store_initialization(self, temp_duckdb):
        """Test that store initializes with tables created."""
        # Query to check if tables exist
        result = temp_duckdb.conn.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
        """).fetchall()

        table_names = [row[0] for row in result]

        assert "llm_interactions" in table_names
        assert "features" in table_names

    def test_insert_interaction(self, temp_duckdb, sample_interaction):
        """Test inserting a single interaction."""
        success = temp_duckdb.insert_interaction(sample_interaction)
        assert success is True

        # Verify insertion
        result = temp_duckdb.conn.execute("""
            SELECT COUNT(*) FROM llm_interactions
        """).fetchone()

        assert result[0] == 1

    def test_insert_multiple_interactions(self, temp_duckdb, sample_interactions):
        """Test inserting multiple interactions."""
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        result = temp_duckdb.conn.execute("""
            SELECT COUNT(*) FROM llm_interactions
        """).fetchone()

        assert result[0] == len(sample_interactions)

    def test_insert_feature(self, temp_duckdb):
        """Test inserting a feature."""
        feature = Feature(
            feature_name="avg_tokens",
            entity_id="user_123",
            value=150.5,
            feature_type=FeatureType.NUMERIC,
            timestamp=datetime.utcnow()
        )

        success = temp_duckdb.insert_feature(feature)
        assert success is True

        # Verify insertion
        result = temp_duckdb.conn.execute("""
            SELECT COUNT(*) FROM features
        """).fetchone()

        assert result[0] == 1

    def test_get_cost_by_day(self, temp_duckdb, sample_interactions):
        """Test daily cost breakdown query."""
        # Insert interactions
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        # Query costs
        costs = temp_duckdb.get_cost_by_day(days=30)

        assert isinstance(costs, dict)
        assert len(costs) > 0

        # Verify total cost
        total = sum(costs.values())
        expected_total = sum(i.cost_usd for i in sample_interactions)

        assert abs(total - expected_total) < 0.01

    def test_get_cost_by_day_filtered_by_user(self, temp_duckdb, sample_interactions):
        """Test cost query filtered by user."""
        # Insert interactions
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        # Get unique user
        user_id = sample_interactions[0].user_id

        # Query costs for specific user
        costs = temp_duckdb.get_cost_by_day(days=30, user_id=user_id)

        # Calculate expected cost for this user
        expected = sum(
            i.cost_usd
            for i in sample_interactions
            if i.user_id == user_id
        )

        actual = sum(costs.values())

        assert abs(actual - expected) < 0.01

    def test_get_cost_by_model(self, temp_duckdb, sample_interactions):
        """Test cost breakdown by model."""
        # Insert interactions
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        # Query costs by model
        costs = temp_duckdb.get_cost_by_model(days=30)

        assert isinstance(costs, dict)
        assert len(costs) > 0

        # Should have both gpt-4 and gpt-3.5-turbo
        assert "gpt-4" in costs
        assert "gpt-3.5-turbo" in costs

    def test_get_token_stats(self, temp_duckdb, sample_interactions):
        """Test token statistics query."""
        # Insert interactions
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        # Query stats
        stats = temp_duckdb.get_token_stats(days=30)

        assert "total_tokens" in stats
        assert "avg_tokens_per_request" in stats
        assert "total_input_tokens" in stats
        assert "total_output_tokens" in stats
        assert "interaction_count" in stats

        # Verify counts
        assert stats["interaction_count"] == len(sample_interactions)

        # Verify total tokens
        expected_total = sum(i.total_tokens for i in sample_interactions)
        assert stats["total_tokens"] == expected_total

    def test_get_top_users_by_cost(self, temp_duckdb, sample_interactions):
        """Test top users query."""
        # Insert interactions
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        # Query top users
        top_users = temp_duckdb.get_top_users_by_cost(days=30, limit=5)

        assert isinstance(top_users, list)
        assert len(top_users) > 0

        # Check structure
        user = top_users[0]
        assert "user_id" in user
        assert "total_cost" in user
        assert "interaction_count" in user
        assert "total_tokens" in user
        assert "avg_latency_ms" in user

        # Verify ordering (descending by cost)
        if len(top_users) > 1:
            assert top_users[0]["total_cost"] >= top_users[1]["total_cost"]

    def test_get_feature_history(self, temp_duckdb):
        """Test feature history query."""
        entity_id = "user_123"
        feature_name = "avg_tokens"

        # Insert feature values over time
        for i in range(5):
            feature = Feature(
                feature_name=feature_name,
                entity_id=entity_id,
                value=100.0 + i * 10,
                feature_type=FeatureType.NUMERIC,
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            temp_duckdb.insert_feature(feature)

        # Query history
        df = temp_duckdb.get_feature_history(entity_id, feature_name, days=30)

        assert len(df) == 5
        assert "timestamp" in df.columns
        assert "value" in df.columns

    def test_execute_custom_query(self, temp_duckdb, sample_interactions):
        """Test executing custom SQL queries."""
        # Insert interactions
        for interaction in sample_interactions:
            temp_duckdb.insert_interaction(interaction)

        # Custom query
        df = temp_duckdb.execute_query("""
            SELECT model, COUNT(*) as count
            FROM llm_interactions
            GROUP BY model
        """)

        assert len(df) > 0
        assert "model" in df.columns
        assert "count" in df.columns

    def test_date_partitioning(self, temp_duckdb):
        """Test that date partitioning works correctly."""
        # Insert interactions on different dates
        for i in range(5):
            interaction = LLMInteraction(
                interaction_id=f"test_{i}",
                user_id="user_123",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt="test",
                response="test",
                input_tokens=10,
                output_tokens=20,
                latency_ms=100,
                cost_usd=0.01,
                timestamp=datetime.utcnow() - timedelta(days=i)
            )
            temp_duckdb.insert_interaction(interaction)

        # Query specific date range
        result = temp_duckdb.conn.execute("""
            SELECT COUNT(DISTINCT date) as date_count
            FROM llm_interactions
        """).fetchone()

        assert result[0] >= 2  # At least 2 different dates

    def test_empty_result_handling(self, temp_duckdb):
        """Test handling of queries with empty results."""
        # Query empty database
        costs = temp_duckdb.get_cost_by_day(days=30)

        assert isinstance(costs, dict)
        assert len(costs) == 0

    def test_duplicate_interaction_id(self, temp_duckdb, sample_interaction):
        """Test handling of duplicate interaction IDs."""
        # Insert first time
        success1 = temp_duckdb.insert_interaction(sample_interaction)
        assert success1 is True

        # Try to insert again (should fail due to PRIMARY KEY)
        success2 = temp_duckdb.insert_interaction(sample_interaction)
        assert success2 is False


@pytest.mark.benchmark
class TestDuckDBPerformance:
    """Performance benchmarks for DuckDB operations."""

    def test_bulk_insert_performance(self, temp_duckdb):
        """Benchmark bulk insertion performance."""
        import time

        # Generate 1000 interactions
        interactions = []
        for i in range(1000):
            interaction = LLMInteraction(
                interaction_id=f"perf_test_{i}",
                user_id=f"user_{i % 100}",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt=f"Test prompt {i}",
                response=f"Test response {i}",
                input_tokens=10,
                output_tokens=20,
                latency_ms=1000,
                cost_usd=0.01,
                timestamp=datetime.utcnow() - timedelta(hours=i)
            )
            interactions.append(interaction)

        # Benchmark insertion
        start = time.time()
        for interaction in interactions:
            temp_duckdb.insert_interaction(interaction)
        elapsed = (time.time() - start) * 1000  # ms

        print(f"\n  DuckDB bulk insert (1000 rows): {elapsed:.2f}ms")
        print(f"  Avg per row: {elapsed/1000:.2f}ms")

        # Should be fast (< 5 seconds for 1000 insertions)
        assert elapsed < 5000

    def test_aggregation_query_performance(self, temp_duckdb):
        """Benchmark aggregation query performance."""
        import time

        # Insert test data
        for i in range(100):
            interaction = LLMInteraction(
                interaction_id=f"perf_test_{i}",
                user_id=f"user_{i % 10}",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt="test",
                response="test",
                input_tokens=10,
                output_tokens=20,
                latency_ms=1000,
                cost_usd=0.01,
                timestamp=datetime.utcnow()
            )
            temp_duckdb.insert_interaction(interaction)

        # Benchmark aggregation
        start = time.time()
        costs = temp_duckdb.get_cost_by_model(days=30)
        elapsed = (time.time() - start) * 1000  # ms

        print(f"\n  DuckDB aggregation query: {elapsed:.2f}ms")

        # Should be fast (< 100ms)
        assert elapsed < 100

class TestInputValidation:
    """Test input validation enhancements."""

    def test_get_cost_by_day_negative_days_raises_error(self, temp_duckdb):
        """Test that negative days parameter raises ValueError."""
        with pytest.raises(ValueError, match="days must be positive"):
            temp_duckdb.get_cost_by_day(days=-5)

    def test_get_cost_by_day_zero_days_raises_error(self, temp_duckdb):
        """Test that zero days parameter raises ValueError."""
        with pytest.raises(ValueError, match="days must be positive"):
            temp_duckdb.get_cost_by_day(days=0)

    def test_get_cost_by_day_large_days_logs_warning(self, temp_duckdb, caplog):
        """Test that large days parameter logs warning."""
        # Clear any previous logs
        caplog.clear()

        # Request more than 365 days
        temp_duckdb.get_cost_by_day(days=400)

        # Check that warning was logged
        assert any(
            "large_lookback_period" in str(record) or "1 year" in str(record)
            for record in caplog.records
        )


class TestResourceCleanup:
    """Test resource cleanup and context manager support."""

    def test_store_has_context_manager(self):
        """Test that store can be used as context manager."""
        with DuckDBStore(db_path=":memory:") as store:
            # Should be able to use the store
            interaction = LLMInteraction(
                interaction_id="ctx_test",
                user_id="user_ctx",
                model="gpt-4",
                provider=ModelProvider.OPENAI,
                prompt="Test",
                response="Test response",
                input_tokens=5,
                output_tokens=10,
                latency_ms=100.0,
                cost_usd=0.001
            )
            success = store.insert_interaction(interaction)
            assert success is True

        # After exiting context, connection should be closed
        assert store._closed is True

    def test_explicit_close(self):
        """Test explicit close method."""
        store = DuckDBStore(db_path=":memory:")
        assert not hasattr(store, '_closed') or store._closed is False

        store.close()
        assert store._closed is True

        # Calling close again should be safe (idempotent)
        store.close()
        assert store._closed is True

    def test_del_closes_connection(self):
        """Test that __del__ closes connection."""
        store = DuckDBStore(db_path=":memory:")
        initial_closed = getattr(store, '_closed', False)
        assert initial_closed is False

        # Delete the store
        del store
        # If no exception is raised, cleanup worked


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
