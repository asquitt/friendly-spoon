"""
Delta Lake Store for Historical Data Storage.

Delta Lake provides:
- ACID transactions on S3
- Time travel (query historical data)
- Schema evolution
- Data versioning

Cost Benefits:
- S3 Standard: $0.023/GB/month
- S3 Intelligent-Tiering: Automatic cost optimization
- No compute costs (unlike data warehouses)

Perfect for:
- Long-term data retention
- Historical analysis
- Compliance and auditing
- Data lake architecture
"""

import os
from typing import List, Optional
from datetime import datetime, timedelta
import pandas as pd
from deltalake import DeltaTable, write_deltalake
import boto3

from ..shared.config import get_config
from ..shared.logger import get_logger
from ..shared.models import LLMInteraction

log = get_logger(__name__)


class DeltaLakeStore:
    """
    Delta Lake-based storage for historical LLM data.

    This store archives interactions for long-term retention.
    Data is partitioned by date for efficient querying.

    Example:
        >>> store = DeltaLakeStore()
        >>> # Write data
        >>> store.write_interactions(interactions)
        >>> # Query historical data
        >>> df = store.read_interactions(start_date="2025-01-01", end_date="2025-01-31")
        >>> print(f"Found {len(df)} interactions")
    """

    def __init__(self, table_path: Optional[str] = None):
        """
        Initialize Delta Lake store.

        Args:
            table_path: S3 or local path to Delta table
                       (e.g., "s3://bucket/delta-lake/interactions")
        """
        config = get_config()

        if table_path is None:
            table_path = config.delta_lake_path

        self.table_path = table_path
        self.config = config

        # Configure S3 client for local MinIO or AWS
        self._setup_s3_client()

        log.info("delta_lake_store_initialized", table_path=table_path)

    def _setup_s3_client(self) -> None:
        """Configure S3 client (MinIO for local, AWS for production)."""
        config = self.config

        if config.use_local_s3:
            # Use MinIO for local development
            os.environ['AWS_ACCESS_KEY_ID'] = config.minio_access_key
            os.environ['AWS_SECRET_ACCESS_KEY'] = config.minio_secret_key
            os.environ['AWS_ENDPOINT_URL'] = config.minio_endpoint
            os.environ['AWS_ALLOW_HTTP'] = 'true'

            log.debug("using_local_s3", endpoint=config.minio_endpoint)
        else:
            # Use AWS S3 for production
            if config.aws_access_key_id:
                os.environ['AWS_ACCESS_KEY_ID'] = config.aws_access_key_id
            if config.aws_secret_access_key:
                os.environ['AWS_SECRET_ACCESS_KEY'] = config.aws_secret_access_key

            log.debug("using_aws_s3", region=config.aws_region)

    def write_interactions(
        self,
        interactions: List[LLMInteraction],
        mode: str = "append"
    ) -> bool:
        """
        Write interactions to Delta Lake.

        Args:
            interactions: List of LLMInteraction objects
            mode: Write mode ("append" or "overwrite")

        Returns:
            bool: True if successful

        Cost Optimization:
            - Data is partitioned by date for efficient queries
            - Only query the partitions you need to minimize data scanned

        Example:
            >>> interactions = [...]  # List of interactions
            >>> store.write_interactions(interactions)
        """
        try:
            if not interactions:
                log.warning("write_interactions_empty", count=0)
                return True

            # Convert to DataFrame
            data = []
            for interaction in interactions:
                data.append({
                    "interaction_id": interaction.interaction_id,
                    "user_id": interaction.user_id,
                    "session_id": interaction.session_id,
                    "model": interaction.model,
                    "provider": interaction.provider.value,
                    "prompt": interaction.prompt,
                    "response": interaction.response,
                    "input_tokens": interaction.input_tokens,
                    "output_tokens": interaction.output_tokens,
                    "total_tokens": interaction.total_tokens,
                    "latency_ms": interaction.latency_ms,
                    "cost_usd": interaction.cost_usd,
                    "timestamp": interaction.timestamp,
                    "date": interaction.timestamp.date(),
                })

            df = pd.DataFrame(data)

            # Write to Delta Lake with date partitioning
            write_deltalake(
                self.table_path,
                df,
                mode=mode,
                partition_by=["date"],
                schema_mode="merge",  # Allow schema evolution
            )

            log.info(
                "interactions_written",
                count=len(interactions),
                table_path=self.table_path
            )
            return True

        except Exception as e:
            log.error("write_interactions_failed", error=str(e))
            return False

    def read_interactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Read interactions from Delta Lake.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            user_id: Filter by user ID
            limit: Maximum rows to return

        Returns:
            pd.DataFrame: Interactions data

        Cost Optimization:
            Partition pruning ensures you only read relevant data!
            - Query 1 day: ~1/365th of data scanned
            - Query 1 month: ~1/12th of data scanned

        Example:
            >>> # Get last week of data
            >>> df = store.read_interactions(
            ...     start_date="2025-01-01",
            ...     end_date="2025-01-07"
            ... )
            >>> print(f"Cost: ${df['cost_usd'].sum():.2f}")
        """
        try:
            # Load Delta table
            dt = DeltaTable(self.table_path)

            # Build filter predicate
            filters = []

            if start_date:
                filters.append(f"date >= '{start_date}'")

            if end_date:
                filters.append(f"date <= '{end_date}'")

            if user_id:
                filters.append(f"user_id = '{user_id}'")

            # Read data with filters
            if filters:
                filter_expr = " AND ".join(filters)
                df = dt.to_pandas(filters=filter_expr)
            else:
                df = dt.to_pandas()

            # Apply limit
            if limit and len(df) > limit:
                df = df.head(limit)

            log.info(
                "interactions_read",
                count=len(df),
                start_date=start_date,
                end_date=end_date
            )

            return df

        except Exception as e:
            log.error("read_interactions_failed", error=str(e))
            return pd.DataFrame()

    def get_history(self) -> List[dict]:
        """
        Get Delta table version history.

        This shows all commits/versions, enabling time travel!

        Returns:
            List[dict]: Version history

        Example:
            >>> history = store.get_history()
            >>> for version in history:
            ...     print(f"Version {version['version']}: {version['timestamp']}")
        """
        try:
            dt = DeltaTable(self.table_path)
            return dt.history()

        except Exception as e:
            log.error("get_history_failed", error=str(e))
            return []

    def time_travel(self, version: int) -> pd.DataFrame:
        """
        Query data from a specific version (time travel).

        This is useful for:
        - Auditing changes
        - Recovering from mistakes
        - Comparing historical states

        Args:
            version: Delta table version number

        Returns:
            pd.DataFrame: Data at that version

        Example:
            >>> # Query data from yesterday
            >>> df = store.time_travel(version=5)
        """
        try:
            dt = DeltaTable(self.table_path, version=version)
            df = dt.to_pandas()

            log.info("time_travel_query", version=version, rows=len(df))
            return df

        except Exception as e:
            log.error("time_travel_failed", error=str(e), version=version)
            return pd.DataFrame()

    def optimize(self) -> bool:
        """
        Optimize Delta table (compaction and cleanup).

        This:
        - Combines small files into larger ones
        - Removes old versions (saves storage costs)
        - Improves query performance

        Run this periodically (e.g., weekly) to optimize costs.

        Returns:
            bool: True if successful

        Example:
            >>> store.optimize()  # Run as part of weekly maintenance
        """
        try:
            dt = DeltaTable(self.table_path)

            # Compact small files
            dt.optimize.compact()

            # Clean up old versions (keep last 30 days)
            retention_hours = 30 * 24
            dt.vacuum(retention_hours=retention_hours)

            log.info("delta_table_optimized", table_path=self.table_path)
            return True

        except Exception as e:
            log.error("optimize_failed", error=str(e))
            return False


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger
    from ..shared.models import ModelProvider

    setup_logger("delta-lake-test", environment="local", debug=True)

    # For testing, use local path instead of S3
    test_path = "/tmp/delta-lake-test"

    store = DeltaLakeStore(table_path=test_path)

    # Create sample interactions
    print("📝 Creating sample interactions...")
    interactions = []
    for i in range(50):
        interaction = LLMInteraction(
            interaction_id=f"int_{i}",
            user_id=f"user_{i % 5}",
            model="gpt-4",
            provider=ModelProvider.OPENAI,
            prompt=f"Test prompt {i}",
            response=f"Test response {i}",
            input_tokens=100,
            output_tokens=50,
            latency_ms=1000.0,
            cost_usd=0.01,
            timestamp=datetime.utcnow() - timedelta(days=i // 10)
        )
        interactions.append(interaction)

    # Write to Delta Lake
    print("💾 Writing to Delta Lake...")
    store.write_interactions(interactions)

    # Read back
    print("\n📖 Reading data...")
    df = store.read_interactions(limit=10)
    print(f"Read {len(df)} rows")
    print(df[["interaction_id", "user_id", "model", "cost_usd"]].head())

    # Check history
    print("\n📜 Version history:")
    history = store.get_history()
    for i, version in enumerate(history):
        print(f"  Version {i}: {version.get('timestamp', 'N/A')}")

    print("\n✅ Delta Lake test complete!")
    print(f"💡 Data stored at: {test_path}")
