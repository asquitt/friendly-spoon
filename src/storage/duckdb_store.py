"""
DuckDB Store for Analytics and OLAP Queries.

DuckDB is an embedded analytical database - think "SQLite for analytics".

Why DuckDB?
- FREE: No costs whatsoever
- FAST: Columnar storage, vectorized execution
- EASY: Single-file database, no server needed
- POWERFUL: Full SQL support, window functions, CTEs

Cost Comparison (1TB of analytical queries per month):
- BigQuery: ~$5,000
- Snowflake: ~$3,000
- DuckDB: $0 (just run it on your server)

Perfect for:
- Feature analytics (trends, distributions, correlations)
- Cost reporting and dashboards
- Drift detection calculations
- Ad-hoc data exploration
"""

import duckdb
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from ..shared.config import get_config
from ..shared.logger import get_logger
from ..shared.models import LLMInteraction, Feature

log = get_logger(__name__)


class DuckDBStore:
    """
    DuckDB-based analytical storage for features and interactions.

    This store is optimized for analytical queries like:
    - Aggregations (AVG, SUM, COUNT, etc.)
    - Time-series analysis
    - Feature correlations
    - Cost breakdowns

    Example:
        >>> store = DuckDBStore()
        >>> # Store interactions
        >>> store.insert_interaction(interaction)
        >>> # Query analytics
        >>> daily_costs = store.get_cost_by_day(days=30)
        >>> print(f"Total: ${sum(daily_costs.values()):.2f}")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize DuckDB store.

        Args:
            db_path: Path to database file (None = in-memory)

        Note:
            For production, use a persistent file path.
            For testing, use in-memory (db_path=None or ":memory:")
        """
        if db_path is None:
            config = get_config()
            db_path = config.duckdb_path

        # Create directory if needed
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self._closed = False

        # Set memory limit (prevents OOM on large queries)
        config = get_config()
        self.conn.execute(f"SET memory_limit='{config.duckdb_memory_limit}'")

        # Create tables
        self._create_tables()

        log.info("duckdb_store_initialized", db_path=db_path)

    def __enter__(self):
        """Context manager entry - return self."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()
        return False

    def __del__(self):
        """Ensure connection is closed on garbage collection."""
        if not self._closed:
            try:
                self.close()
            except Exception:
                pass  # Ignore errors during cleanup

    def close(self) -> None:
        """
        Close database connection.

        Safe to call multiple times (idempotent).
        """
        if not self._closed:
            try:
                self.conn.close()
                log.info("duckdb_store_closed", db_path=self.db_path)
            except Exception as e:
                log.warning("duckdb_store_close_error", error=str(e))
            finally:
                self._closed = True

    def _create_tables(self) -> None:
        """
        Create tables for storing features and interactions.

        Schema design notes:
        - Partitioned by date for efficient time-range queries
        - Indexed on frequently-queried columns
        - Columnar storage for fast aggregations
        """

        # Table for LLM interactions
        self.conn.execute(f"""
            CREATE TABLE IF NOT EXISTS llm_interactions (
                interaction_id VARCHAR PRIMARY KEY,
                user_id VARCHAR NOT NULL,
                session_id VARCHAR,
                model VARCHAR NOT NULL,
                provider VARCHAR NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                latency_ms DOUBLE NOT NULL,
                cost_usd DOUBLE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                date DATE NOT NULL,  -- Partition key
                metadata JSON
            )
        """)

        # Create indexes for common queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_date
            ON llm_interactions(date)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_user
            ON llm_interactions(user_id, date)
        """)

        # Table for computed features
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS features (
                feature_name VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                value VARCHAR NOT NULL,  -- Store as string, parse as needed
                feature_type VARCHAR NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                date DATE NOT NULL,  -- Partition key
                version INTEGER NOT NULL,
                metadata JSON,
                PRIMARY KEY (feature_name, entity_id, timestamp)
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_features_entity
            ON features(entity_id, feature_name, date)
        """)

        log.debug("duckdb_tables_created")

    def insert_interaction(self, interaction: LLMInteraction) -> bool:
        """
        Insert an LLM interaction.

        Args:
            interaction: LLMInteraction object

        Returns:
            bool: True if successful

        Example:
            >>> interaction = LLMInteraction(...)
            >>> store.insert_interaction(interaction)
        """
        try:
            self.conn.execute("""
                INSERT INTO llm_interactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                interaction.interaction_id,
                interaction.user_id,
                interaction.session_id,
                interaction.model,
                interaction.provider.value,
                interaction.prompt,
                interaction.response,
                interaction.input_tokens,
                interaction.output_tokens,
                interaction.total_tokens,
                interaction.latency_ms,
                interaction.cost_usd,
                interaction.timestamp,
                interaction.timestamp.date(),
                interaction.metadata if interaction.metadata else {}
            ])

            log.debug(
                "interaction_inserted",
                interaction_id=interaction.interaction_id,
                user_id=interaction.user_id
            )
            return True

        except Exception as e:
            log.error(
                "insert_interaction_failed",
                error=str(e),
                interaction_id=interaction.interaction_id
            )
            return False

    def insert_feature(self, feature: Feature) -> bool:
        """
        Insert a computed feature.

        Args:
            feature: Feature object

        Returns:
            bool: True if successful
        """
        try:
            # Convert value to string for storage
            value_str = str(feature.value)

            self.conn.execute("""
                INSERT INTO features VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                feature.feature_name,
                feature.entity_id,
                value_str,
                feature.feature_type.value,
                feature.timestamp,
                feature.timestamp.date(),
                feature.version,
                feature.metadata if feature.metadata else {}
            ])

            log.debug(
                "feature_inserted",
                feature_name=feature.feature_name,
                entity_id=feature.entity_id
            )
            return True

        except Exception as e:
            log.error(
                "insert_feature_failed",
                error=str(e),
                feature_name=feature.feature_name
            )
            return False

    def get_cost_by_day(
        self,
        days: int = 30,
        user_id: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Get daily cost breakdown.

        Args:
            days: Number of days to look back
            user_id: Optional filter by user

        Returns:
            Dict[str, float]: Date -> cost mapping

        Example:
            >>> costs = store.get_cost_by_day(days=7)
            >>> for date, cost in costs.items():
            ...     print(f"{date}: ${cost:.2f}")
        """
        # Input validation
        if days <= 0:
            raise ValueError(f"days must be positive, got {days}")
        if days > 365:
            log.warning("large_lookback_period", days=days,
                       message="Requesting >1 year of data may be slow")

        try:
            # Note: DuckDB doesn't support ? placeholders in INTERVAL, so we use f-string
            query = f"""
                SELECT
                    date::VARCHAR as date,
                    SUM(cost_usd) as total_cost
                FROM llm_interactions
                WHERE date >= CURRENT_DATE - INTERVAL '{days}' DAY
            """

            params = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            query += " GROUP BY date ORDER BY date"

            if params:
                result = self.conn.execute(query, params).fetchall()
            else:
                result = self.conn.execute(query).fetchall()

            return {row[0]: float(row[1]) for row in result}

        except Exception as e:
            log.error("get_cost_by_day_failed", error=str(e))
            return {}

    def get_cost_by_model(
        self,
        days: int = 30
    ) -> Dict[str, float]:
        """
        Get cost breakdown by model.

        Args:
            days: Number of days to look back

        Returns:
            Dict[str, float]: Model -> cost mapping

        Example:
            >>> costs = store.get_cost_by_model(days=30)
            >>> for model, cost in sorted(costs.items(), key=lambda x: -x[1]):
            ...     print(f"{model}: ${cost:.2f}")
        """
        try:
            result = self.conn.execute(f"""
                SELECT
                    model,
                    SUM(cost_usd) as total_cost
                FROM llm_interactions
                WHERE date >= CURRENT_DATE - INTERVAL '{days}' DAY
                GROUP BY model
                ORDER BY total_cost DESC
            """).fetchall()

            return {row[0]: float(row[1]) for row in result}

        except Exception as e:
            log.error("get_cost_by_model_failed", error=str(e))
            return {}

    def get_token_stats(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get token usage statistics.

        Args:
            days: Number of days to look back

        Returns:
            Dict[str, Any]: Token statistics

        Example:
            >>> stats = store.get_token_stats(days=7)
            >>> print(f"Total tokens: {stats['total_tokens']:,}")
            >>> print(f"Avg per request: {stats['avg_tokens_per_request']:.1f}")
        """
        try:
            result = self.conn.execute(f"""
                SELECT
                    SUM(total_tokens) as total_tokens,
                    AVG(total_tokens) as avg_tokens,
                    SUM(input_tokens) as total_input,
                    SUM(output_tokens) as total_output,
                    COUNT(*) as interaction_count
                FROM llm_interactions
                WHERE date >= CURRENT_DATE - INTERVAL '{days}' DAY
            """).fetchone()

            if result:
                return {
                    "total_tokens": int(result[0] or 0),
                    "avg_tokens_per_request": float(result[1] or 0),
                    "total_input_tokens": int(result[2] or 0),
                    "total_output_tokens": int(result[3] or 0),
                    "interaction_count": int(result[4] or 0),
                }

            return {}

        except Exception as e:
            log.error("get_token_stats_failed", error=str(e))
            return {}

    def get_feature_history(
        self,
        entity_id: str,
        feature_name: str,
        days: int = 30
    ) -> pd.DataFrame:
        """
        Get feature value history over time.

        This is useful for:
        - Visualizing feature trends
        - Detecting drift
        - Understanding user behavior changes

        Args:
            entity_id: Entity ID
            feature_name: Feature name
            days: Number of days to look back

        Returns:
            pd.DataFrame: Feature history with columns [timestamp, value]

        Example:
            >>> df = store.get_feature_history("user_123", "avg_prompt_length", days=30)
            >>> df.plot(x='timestamp', y='value', title='Prompt Length Over Time')
        """
        try:
            result = self.conn.execute(f"""
                SELECT
                    timestamp,
                    value
                FROM features
                WHERE entity_id = ?
                    AND feature_name = ?
                    AND date >= CURRENT_DATE - INTERVAL '{days}' DAY
                ORDER BY timestamp
            """, [entity_id, feature_name]).fetchdf()

            return result

        except Exception as e:
            log.error(
                "get_feature_history_failed",
                error=str(e),
                entity_id=entity_id,
                feature_name=feature_name
            )
            return pd.DataFrame()

    def get_top_users_by_cost(
        self,
        days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top users by cost (for identifying high-value or high-cost users).

        Args:
            days: Number of days to look back
            limit: Number of users to return

        Returns:
            List[Dict]: User statistics

        Example:
            >>> top_users = store.get_top_users_by_cost(days=30, limit=5)
            >>> for user in top_users:
            ...     print(f"{user['user_id']}: ${user['total_cost']:.2f}")
        """
        try:
            result = self.conn.execute(f"""
                SELECT
                    user_id,
                    SUM(cost_usd) as total_cost,
                    COUNT(*) as interaction_count,
                    SUM(total_tokens) as total_tokens,
                    AVG(latency_ms) as avg_latency
                FROM llm_interactions
                WHERE date >= CURRENT_DATE - INTERVAL '{days}' DAY
                GROUP BY user_id
                ORDER BY total_cost DESC
                LIMIT ?
            """, [limit]).fetchall()

            return [
                {
                    "user_id": row[0],
                    "total_cost": float(row[1]),
                    "interaction_count": int(row[2]),
                    "total_tokens": int(row[3]),
                    "avg_latency_ms": float(row[4]),
                }
                for row in result
            ]

        except Exception as e:
            log.error("get_top_users_by_cost_failed", error=str(e))
            return []

    def execute_query(self, query: str, params: Optional[List] = None) -> pd.DataFrame:
        """
        Execute arbitrary SQL query.

        Args:
            query: SQL query
            params: Optional query parameters

        Returns:
            pd.DataFrame: Query results

        Warning:
            Be careful with this method in production!
            Validate and sanitize user inputs.

        Example:
            >>> df = store.execute_query('''
            ...     SELECT model, AVG(latency_ms) as avg_latency
            ...     FROM llm_interactions
            ...     WHERE date >= CURRENT_DATE - 7
            ...     GROUP BY model
            ... ''')
        """
        try:
            if params:
                return self.conn.execute(query, params).fetchdf()
            else:
                return self.conn.execute(query).fetchdf()

        except Exception as e:
            log.error("execute_query_failed", error=str(e), query=query[:100])
            return pd.DataFrame()

# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger
    from ..shared.models import ModelProvider

    setup_logger("duckdb-test", environment="local", debug=True)

    # Initialize store
    store = DuckDBStore(db_path=":memory:")  # In-memory for testing

    # Insert sample interactions
    print("📝 Inserting sample interactions...")
    for i in range(100):
        interaction = LLMInteraction(
            interaction_id=f"int_{i}",
            user_id=f"user_{i % 10}",  # 10 users
            model="gpt-4" if i % 2 == 0 else "gpt-3.5-turbo",
            provider=ModelProvider.OPENAI,
            prompt=f"Test prompt {i}",
            response=f"Test response {i}",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1000.0 + i,
            cost_usd=0.01 if i % 2 == 0 else 0.001,
            timestamp=datetime.utcnow() - timedelta(days=i // 10)
        )
        store.insert_interaction(interaction)

    # Query analytics
    print("\n💰 Cost by model:")
    costs = store.get_cost_by_model(days=30)
    for model, cost in costs.items():
        print(f"  {model}: ${cost:.2f}")

    print("\n📊 Token statistics:")
    stats = store.get_token_stats(days=30)
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n👥 Top users by cost:")
    top_users = store.get_top_users_by_cost(days=30, limit=5)
    for user in top_users:
        print(f"  {user['user_id']}: ${user['total_cost']:.2f}")

    print("\n✅ DuckDB store test complete!")
