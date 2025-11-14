"""
Week 1 Starter: Configuration Management

Your task: Create a configuration system using Pydantic Settings.

Learning goals:
- Load configuration from environment variables
- Use .env files for local development
- Provide sensible defaults
- Validate configuration values
- Make configuration testable

Run tests: pytest ../tests/test_config.py -v
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


# =============================================================================
# Exercise 1.3: Application Settings
# =============================================================================

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This class automatically loads configuration from:
    1. Environment variables (highest priority)
    2. .env file (if it exists)
    3. Default values (lowest priority)

    Example usage:
        settings = Settings()
        print(settings.redis_host)  # Loaded from REDIS_HOST or default
    """

    # === Redis Configuration ===
    # TODO: Add redis_host field
    # Type: str, default: "localhost"

    # TODO: Add redis_port field
    # Type: int, default: 6379

    # TODO: Add redis_password field
    # Type: str, default: "" (empty string)

    # TODO: Add redis_db field
    # Type: int, default: 0

    # === DuckDB Configuration ===
    # TODO: Add duckdb_path field
    # Type: str, default: ":memory:"
    # Note: ":memory:" creates an in-memory database (great for testing!)

    # === S3/MinIO Configuration ===
    # TODO: Add aws_access_key_id field
    # Type: str, default: "minioadmin"

    # TODO: Add aws_secret_access_key field
    # Type: str, default: "minioadmin"

    # TODO: Add aws_endpoint_url field
    # Type: Optional[str], default: None
    # Note: Only needed for MinIO/local S3

    # TODO: Add aws_region field
    # Type: str, default: "us-east-1"

    # TODO: Add s3_bucket_features field
    # Type: str, default: "features"

    # === Kafka Configuration ===
    # TODO: Add kafka_bootstrap_servers field
    # Type: str, default: "localhost:9092"

    # TODO: Add kafka_topic_embeddings field
    # Type: str, default: "embeddings"

    # TODO: Add kafka_topic_features field
    # Type: str, default: "features"

    # === Embedding Model Configuration ===
    # TODO: Add embedding_model field
    # Type: str, default: "all-MiniLM-L6-v2"
    # Note: This is a small, fast model from sentence-transformers

    # TODO: Add embedding_dimension field
    # Type: int, default: 384
    # Note: Dimension of all-MiniLM-L6-v2 model

    # TODO: Add embedding_batch_size field
    # Type: int, default: 32

    # === Feature Store Configuration ===
    # TODO: Add feature_store_name field
    # Type: str, default: "llm_features"

    # TODO: Add feature_ttl_seconds field
    # Type: int, default: 3600 (1 hour)

    # === Logging Configuration ===
    # TODO: Add log_level field
    # Type: str, default: "INFO"
    # Valid values: DEBUG, INFO, WARNING, ERROR, CRITICAL

    # TODO: Add log_format field
    # Type: str, default: "json"
    # Valid values: json, console

    # === Model Configuration ===
    # TODO: Add model_config using SettingsConfigDict
    # Should specify:
    # - env_file: ".env"
    # - env_file_encoding: "utf-8"
    # - case_sensitive: False
    #
    # Example:
    # model_config = SettingsConfigDict(
    #     env_file=".env",
    #     env_file_encoding="utf-8",
    #     case_sensitive=False
    # )

    pass  # Remove this when you add your code


# =============================================================================
# Helper Functions
# =============================================================================

def get_settings() -> Settings:
    """
    Get application settings.

    This is a factory function that creates and returns settings.
    Using a function allows for easy testing and mocking.

    Returns:
        Settings: Application settings instance
    """
    # TODO: Create and return Settings instance
    # return Settings()

    pass  # Remove this when you add your code


def print_settings(settings: Settings) -> None:
    """
    Print all settings (useful for debugging).

    Args:
        settings: Settings instance to print

    Note: In production, be careful not to print sensitive values!
    """
    print("=" * 80)
    print("Current Settings:")
    print("=" * 80)

    # TODO: Print all settings
    # Hint: Use settings.model_dump() to get all values as a dict
    # Hint: Mask sensitive values like passwords!
    #
    # Example:
    # for key, value in settings.model_dump().items():
    #     if "password" in key.lower() or "secret" in key.lower():
    #         print(f"{key}: {'*' * 8}")
    #     else:
    #         print(f"{key}: {value}")

    pass  # Remove this when you add your code


# =============================================================================
# Exercise 1.8: Configuration Validation (Intermediate)
# =============================================================================

class ValidatedSettings(Settings):
    """
    Settings with additional validation.

    Requirements:
    - log_level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - embedding_dimension must be > 0
    - redis_port must be between 1 and 65535
    - kafka_bootstrap_servers must not be empty
    """

    # TODO: Add validators for the fields above
    # Hint: Use @field_validator decorator
    # Hint: Raise ValueError with helpful messages

    pass  # Remove this when you add your code


# =============================================================================
# Demo
# =============================================================================

def main():
    """
    Demo: Load and display configuration.

    Run this file to test your implementation:
        python starter/config.py

    Try it with environment variables:
        REDIS_HOST=192.168.1.100 python starter/config.py
    """
    print("=" * 80)
    print("Week 1: Configuration Management Demo")
    print("=" * 80)

    # TODO: Load settings
    # settings = get_settings()

    # TODO: Print settings
    # print_settings(settings)

    # TODO: Show environment variable override
    # import os
    # os.environ["REDIS_HOST"] = "custom.redis.com"
    # settings2 = get_settings()
    # print("\nAfter setting REDIS_HOST environment variable:")
    # print(f"redis_host: {settings2.redis_host}")

    print("\n✅ If you see settings above, your config system is working!")
    print("Run tests with: pytest ../tests/test_config.py -v")


if __name__ == "__main__":
    main()
