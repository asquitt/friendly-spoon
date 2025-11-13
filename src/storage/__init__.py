"""
Storage Layer for LLM Feature Store.

This module provides:
- Feature Store (online + offline features)
- Caching layer (Redis)
- Analytics database (DuckDB)
- Historical storage (Delta Lake)

Cost Efficiency:
- Hot tier (Redis/DynamoDB): Fast but expensive, only for active features
- Warm tier (DuckDB): Fast analytics, zero cost
- Cold tier (Delta Lake on S3): Cheap long-term storage ($0.023/GB/month)
"""

from .feature_store import FeatureStore
from .cache import CacheManager
from .duckdb_store import DuckDBStore
from .delta_lake_store import DeltaLakeStore

__all__ = [
    "FeatureStore",
    "CacheManager",
    "DuckDBStore",
    "DeltaLakeStore",
]
