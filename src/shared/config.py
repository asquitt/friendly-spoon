"""
Configuration Management for LLM Feature Store.

This module centralizes all configuration settings and makes it easy to switch
between local development and production environments.

Key features:
- Environment-based configuration (dev/prod)
- Type-safe settings with Pydantic
- Sensible defaults for local development
- Cost optimization settings
"""

from functools import lru_cache
from typing import Literal, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    All settings can be overridden via environment variables.
    Example: ENVIRONMENT=production python app.py

    Cost Optimization Tips:
    - Use 'local' environment for development (zero cloud costs)
    - Enable caching to reduce embedding API calls
    - Set appropriate TTLs to balance freshness vs cost
    """

    # ==========================================================================
    # Environment Configuration
    # ==========================================================================
    environment: Literal["local", "development", "staging", "production"] = Field(
        default="local",
        description="Deployment environment. 'local' uses Docker services."
    )

    debug: bool = Field(
        default=True,
        description="Enable debug logging"
    )

    # ==========================================================================
    # Kafka Configuration
    # ==========================================================================
    kafka_bootstrap_servers: str = Field(
        default="localhost:9094",
        description="Kafka broker addresses (comma-separated)"
    )

    kafka_topic_interactions: str = Field(
        default="llm-interactions",
        description="Topic for LLM interaction events"
    )

    kafka_topic_embeddings: str = Field(
        default="embedding-requests",
        description="Topic for embedding generation requests"
    )

    kafka_consumer_group: str = Field(
        default="feature-store-consumers",
        description="Consumer group ID"
    )

    # Cost Tip: Adjust batch size to balance latency vs efficiency
    kafka_batch_size: int = Field(
        default=100,
        description="Number of messages to batch before processing"
    )

    # ==========================================================================
    # Redis Configuration (Caching)
    # ==========================================================================
    redis_host: str = Field(
        default="localhost",
        description="Redis host for caching"
    )

    redis_port: int = Field(
        default=6379,
        description="Redis port"
    )

    redis_db: int = Field(
        default=0,
        description="Redis database number"
    )

    # Cost Optimization: Cache embeddings for 24 hours by default
    # Typical cache hit rate: 95%+ = 95% cost savings on embeddings!
    embedding_cache_ttl: int = Field(
        default=86400,  # 24 hours in seconds
        description="How long to cache embeddings (seconds)"
    )

    feature_cache_ttl: int = Field(
        default=300,  # 5 minutes
        description="How long to cache feature values (seconds)"
    )

    # ==========================================================================
    # DuckDB Configuration (Analytics)
    # ==========================================================================
    duckdb_path: str = Field(
        default="data/feature_store.duckdb",
        description="Path to DuckDB database file"
    )

    # Cost Tip: DuckDB is free! Use it for all analytics workloads
    duckdb_memory_limit: str = Field(
        default="1GB",
        description="Memory limit for DuckDB queries"
    )

    # ==========================================================================
    # Delta Lake Configuration (Historical Storage)
    # ==========================================================================
    delta_lake_path: str = Field(
        default="s3://feature-store/delta-lake",
        description="S3 path for Delta Lake (or local path for dev)"
    )

    # For local development, override to use MinIO
    use_local_s3: bool = Field(
        default=True,
        description="Use local MinIO instead of AWS S3"
    )

    minio_endpoint: str = Field(
        default="http://localhost:9000",
        description="MinIO endpoint for local S3"
    )

    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )

    minio_secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )

    # ==========================================================================
    # AWS Configuration (Production)
    # ==========================================================================
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region"
    )

    aws_access_key_id: Optional[str] = Field(
        default=None,
        description="AWS access key (optional, uses IAM role if not set)"
    )

    aws_secret_access_key: Optional[str] = Field(
        default=None,
        description="AWS secret key (optional)"
    )

    # DynamoDB for low-latency feature serving
    dynamodb_table_name: str = Field(
        default="llm-features",
        description="DynamoDB table for online features"
    )

    # Cost Optimization: Use on-demand billing for unpredictable workloads
    dynamodb_billing_mode: Literal["PROVISIONED", "PAY_PER_REQUEST"] = Field(
        default="PAY_PER_REQUEST",
        description="DynamoDB billing mode"
    )

    # ==========================================================================
    # Embedding Model Configuration
    # ==========================================================================
    # Cost Analysis:
    # - Local model (sentence-transformers): $0 per embedding
    # - OpenAI text-embedding-ada-002: ~$0.0001 per 1K tokens
    # - For 1M embeddings/month: $0 vs $100 = 100% savings!

    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model name"
    )

    embedding_model_device: Literal["cpu", "cuda"] = Field(
        default="cpu",
        description="Device for embedding model (cpu or cuda)"
    )

    embedding_batch_size: int = Field(
        default=32,
        description="Batch size for embedding generation"
    )

    # Alternative: Use OpenAI embeddings (requires API key and costs money)
    use_openai_embeddings: bool = Field(
        default=False,
        description="Use OpenAI embeddings instead of local model"
    )

    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (if using OpenAI embeddings)"
    )

    # ==========================================================================
    # Temporal Configuration (Workflow Orchestration)
    # ==========================================================================
    temporal_host: str = Field(
        default="localhost:7233",
        description="Temporal server address"
    )

    temporal_namespace: str = Field(
        default="default",
        description="Temporal namespace"
    )

    temporal_task_queue: str = Field(
        default="feature-store-tasks",
        description="Temporal task queue name"
    )

    # ==========================================================================
    # OpenFaaS Configuration (Serverless Functions)
    # ==========================================================================
    openfaas_gateway: str = Field(
        default="http://localhost:8083",
        description="OpenFaaS gateway URL"
    )

    # ==========================================================================
    # Feature Drift Detection Configuration
    # ==========================================================================
    drift_detection_window_days: int = Field(
        default=7,
        description="Historical window for drift detection (days)"
    )

    drift_detection_threshold: float = Field(
        default=0.1,
        description="PSI threshold for drift detection (0.1 = 10% change)"
    )

    drift_check_interval_hours: int = Field(
        default=6,
        description="How often to check for drift (hours)"
    )

    # ==========================================================================
    # Monitoring & Alerting Configuration
    # ==========================================================================
    prometheus_port: int = Field(
        default=9090,
        description="Prometheus metrics port"
    )

    enable_slack_alerts: bool = Field(
        default=False,
        description="Enable Slack notifications"
    )

    slack_webhook_url: Optional[str] = Field(
        default=None,
        description="Slack webhook URL for alerts"
    )

    enable_pagerduty_alerts: bool = Field(
        default=False,
        description="Enable PagerDuty alerts"
    )

    pagerduty_api_key: Optional[str] = Field(
        default=None,
        description="PagerDuty API key"
    )

    # ==========================================================================
    # Cost Tracking Configuration
    # ==========================================================================
    enable_cost_tracking: bool = Field(
        default=True,
        description="Track LLM API costs"
    )

    # Cost per token for different models (as of 2025)
    # Update these values based on current pricing
    cost_per_1k_input_tokens: dict = Field(
        default={
            "gpt-4": 0.03,
            "gpt-4-32k": 0.06,
            "gpt-3.5-turbo": 0.0015,
            "claude-3-opus": 0.015,
            "claude-3-sonnet": 0.003,
        },
        description="Cost per 1K input tokens by model"
    )

    cost_per_1k_output_tokens: dict = Field(
        default={
            "gpt-4": 0.06,
            "gpt-4-32k": 0.12,
            "gpt-3.5-turbo": 0.002,
            "claude-3-opus": 0.075,
            "claude-3-sonnet": 0.015,
        },
        description="Cost per 1K output tokens by model"
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


@lru_cache()
def get_config() -> Settings:
    """
    Get application configuration (cached).

    This function loads settings once and caches them for the application lifetime.
    To reload settings, restart the application.

    Returns:
        Settings: Application configuration object

    Example:
        >>> config = get_config()
        >>> print(config.kafka_bootstrap_servers)
        localhost:9094

    Cost Optimization Note:
        The default configuration is optimized for local development (zero cost).
        For production, set environment variables to point to cloud services.
    """
    return Settings()


def get_cost_estimate(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Estimate the cost of an LLM API call.

    Args:
        model: Model name (e.g., "gpt-4", "claude-3-sonnet")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        float: Estimated cost in USD

    Example:
        >>> cost = get_cost_estimate("gpt-4", 100, 50)
        >>> print(f"${cost:.4f}")
        $0.0060

    This helps you track and optimize LLM costs in real-time!
    """
    config = get_config()

    input_cost = (
        input_tokens / 1000 *
        config.cost_per_1k_input_tokens.get(model, 0)
    )

    output_cost = (
        output_tokens / 1000 *
        config.cost_per_1k_output_tokens.get(model, 0)
    )

    return input_cost + output_cost


if __name__ == "__main__":
    # Test configuration loading
    config = get_config()
    print(f"Environment: {config.environment}")
    print(f"Kafka servers: {config.kafka_bootstrap_servers}")
    print(f"Redis host: {config.redis_host}")
    print(f"Embedding model: {config.embedding_model}")
    print("\n💰 Cost estimate for 100 input + 50 output tokens:")
    print(f"  GPT-4: ${get_cost_estimate('gpt-4', 100, 50):.4f}")
    print(f"  GPT-3.5: ${get_cost_estimate('gpt-3.5-turbo', 100, 50):.4f}")
    print(f"  Claude Sonnet: ${get_cost_estimate('claude-3-sonnet', 100, 50):.4f}")
