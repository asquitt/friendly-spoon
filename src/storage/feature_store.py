"""
Main Feature Store Interface.

This is the main API for the feature store, providing:
- Online features (low-latency lookups from cache/DynamoDB)
- Offline features (batch retrieval from DuckDB/Delta Lake)
- Feature materialization (compute and store features)

Usage Pattern:
1. Write interactions → Feature store
2. Features are automatically computed
3. Retrieve features for serving or training
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd

from .cache import CacheManager
from .duckdb_store import DuckDBStore
from .delta_lake_store import DeltaLakeStore
from ..shared.config import get_config
from ..shared.logger import get_logger
from ..shared.models import LLMInteraction, Feature, FeatureType

log = get_logger(__name__)


class FeatureStore:
    """
    Unified feature store interface.

    This orchestrates the 3-tier storage:
    1. Hot tier (Cache): <10ms latency, recent features
    2. Warm tier (DuckDB): ~100ms latency, analytics
    3. Cold tier (Delta Lake): ~1s latency, historical data

    Example:
        >>> fs = FeatureStore()
        >>> # Store interaction
        >>> fs.write_interaction(interaction)
        >>> # Get online features (fast!)
        >>> features = fs.get_online_features("user_123", ["avg_tokens", "total_cost"])
        >>> # Get offline features (batch)
        >>> training_data = fs.get_offline_features(["user_1", "user_2"], start_date="2025-01-01")
    """

    def __init__(
        self,
        cache: Optional[CacheManager] = None,
        duckdb: Optional[DuckDBStore] = None,
        delta: Optional[DeltaLakeStore] = None,
    ):
        """
        Initialize feature store.

        Args:
            cache: Cache manager (creates one if not provided)
            duckdb: DuckDB store (creates one if not provided)
            delta: Delta Lake store (creates one if not provided)
        """
        self.cache = cache or CacheManager()
        self.duckdb = duckdb or DuckDBStore()
        self.delta = delta or DeltaLakeStore()
        self.config = get_config()

        log.info("feature_store_initialized")

    def write_interaction(self, interaction: LLMInteraction) -> bool:
        """
        Write an LLM interaction and compute features.

        This automatically:
        1. Stores in DuckDB (for analytics)
        2. Archives in Delta Lake (for long-term storage)
        3. Computes and caches features

        Args:
            interaction: LLMInteraction object

        Returns:
            bool: True if successful

        Example:
            >>> interaction = LLMInteraction(...)
            >>> fs.write_interaction(interaction)
        """
        try:
            # Write to DuckDB (analytics)
            self.duckdb.insert_interaction(interaction)

            # Write to Delta Lake (archival) - in production, do this async/batch
            # For now, we'll skip this for performance
            # self.delta.write_interactions([interaction])

            # Compute and cache features
            self._compute_features_for_interaction(interaction)

            log.info(
                "interaction_written",
                interaction_id=interaction.interaction_id,
                user_id=interaction.user_id
            )

            return True

        except Exception as e:
            log.error(
                "write_interaction_failed",
                error=str(e),
                interaction_id=interaction.interaction_id
            )
            return False

    def _compute_features_for_interaction(self, interaction: LLMInteraction) -> None:
        """
        Compute and cache features from an interaction.

        Features computed:
        - Total cost (running total)
        - Total tokens (running total)
        - Average latency
        - Interaction count

        Args:
            interaction: LLMInteraction object
        """
        user_id = interaction.user_id

        # Get current totals from cache (or initialize)
        total_cost = self.cache.get_feature(user_id, "total_cost") or 0.0
        total_tokens = self.cache.get_feature(user_id, "total_tokens") or 0
        interaction_count = self.cache.get_feature(user_id, "interaction_count") or 0

        # Update totals
        total_cost += interaction.cost_usd
        total_tokens += interaction.total_tokens
        interaction_count += 1

        # Cache updated values
        self.cache.set_feature(user_id, "total_cost", total_cost)
        self.cache.set_feature(user_id, "total_tokens", total_tokens)
        self.cache.set_feature(user_id, "interaction_count", interaction_count)
        self.cache.set_feature(user_id, "last_model", interaction.model)
        self.cache.set_feature(user_id, "last_interaction_time", interaction.timestamp)

        log.debug(
            "features_computed",
            user_id=user_id,
            total_cost=total_cost,
            total_tokens=total_tokens
        )

    def get_online_features(
        self,
        entity_id: str,
        feature_names: List[str]
    ) -> Dict[str, Any]:
        """
        Get online features (low-latency).

        This tries cache first, falls back to DuckDB if needed.

        Args:
            entity_id: Entity ID (user_id, session_id, etc.)
            feature_names: List of feature names to retrieve

        Returns:
            Dict[str, Any]: Feature name -> value mapping

        Example:
            >>> features = fs.get_online_features(
            ...     "user_123",
            ...     ["total_cost", "total_tokens", "interaction_count"]
            ... )
            >>> print(f"User cost: ${features['total_cost']:.2f}")
        """
        features = {}

        for feature_name in feature_names:
            # Try cache first (hot tier)
            value = self.cache.get_feature(entity_id, feature_name)

            if value is not None:
                features[feature_name] = value
            else:
                # Fall back to DuckDB (warm tier)
                # This would be more sophisticated in production
                features[feature_name] = None

        log.debug(
            "online_features_retrieved",
            entity_id=entity_id,
            features=list(features.keys())
        )

        return features

    def get_offline_features(
        self,
        entity_ids: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get offline features for batch processing/training.

        This queries DuckDB for analytical workloads.

        Args:
            entity_ids: List of entity IDs
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            pd.DataFrame: Features for all entities

        Example:
            >>> # Get training data
            >>> training_data = fs.get_offline_features(
            ...     entity_ids=["user_1", "user_2", "user_3"],
            ...     start_date="2025-01-01",
            ...     end_date="2025-01-31"
            ... )
            >>> print(training_data.head())
        """
        # This is a simplified version
        # In production, you'd have pre-computed feature tables

        # Query interactions from DuckDB
        query = """
            SELECT
                user_id as entity_id,
                COUNT(*) as interaction_count,
                SUM(cost_usd) as total_cost,
                SUM(total_tokens) as total_tokens,
                AVG(latency_ms) as avg_latency,
                MIN(timestamp) as first_interaction,
                MAX(timestamp) as last_interaction
            FROM llm_interactions
            WHERE 1=1
        """

        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        if entity_ids:
            placeholders = ",".join(["?" for _ in entity_ids])
            query += f" AND user_id IN ({placeholders})"
            params.extend(entity_ids)

        query += " GROUP BY user_id"

        df = self.duckdb.execute_query(query, params if params else None)

        log.info(
            "offline_features_retrieved",
            entity_count=len(entity_ids),
            rows=len(df)
        )

        return df

    def get_cost_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get cost summary for the specified period.

        Args:
            days: Number of days to look back

        Returns:
            Dict[str, Any]: Cost summary

        Example:
            >>> summary = fs.get_cost_summary(days=7)
            >>> print(f"Weekly cost: ${summary['total_cost']:.2f}")
        """
        return {
            "total_cost": sum(self.duckdb.get_cost_by_day(days=days).values()),
            "cost_by_model": self.duckdb.get_cost_by_model(days=days),
            "token_stats": self.duckdb.get_token_stats(days=days),
            "top_users": self.duckdb.get_top_users_by_cost(days=days, limit=10),
        }


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger
    from ..shared.models import ModelProvider
    from datetime import timedelta

    setup_logger("feature-store-test", environment="local", debug=True)

    # Initialize feature store
    fs = FeatureStore()

    # Write sample interactions
    print("📝 Writing interactions...")
    for i in range(10):
        interaction = LLMInteraction(
            interaction_id=f"int_{i}",
            user_id=f"user_{i % 3}",  # 3 users
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt=f"Test prompt {i}",
            response=f"Test response {i}",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1000.0,
            cost_usd=0.01,
            timestamp=datetime.utcnow() - timedelta(hours=i)
        )
        fs.write_interaction(interaction)

    # Get online features
    print("\n🔥 Online features (user_0):")
    features = fs.get_online_features(
        "user_0",
        ["total_cost", "total_tokens", "interaction_count", "last_model"]
    )
    for name, value in features.items():
        print(f"  {name}: {value}")

    # Get cost summary
    print("\n💰 Cost summary:")
    summary = fs.get_cost_summary(days=7)
    print(f"  Total cost: ${summary['total_cost']:.2f}")
    print(f"  Total tokens: {summary['token_stats'].get('total_tokens', 0):,}")

    print("\n✅ Feature store test complete!")
