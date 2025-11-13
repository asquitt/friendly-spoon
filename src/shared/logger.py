"""
Structured Logging for LLM Feature Store.

This module provides structured logging with:
- JSON output for easy parsing
- Contextual information (request IDs, user IDs, etc.)
- Cost tracking integration
- Performance metrics

Why structured logging?
- Easy to search and analyze in production
- Integrates well with log aggregation tools (CloudWatch, Datadog, etc.)
- Helps track down cost and performance issues
"""

import sys
import logging
import structlog
from typing import Any, Dict, Optional
from datetime import datetime


def setup_logger(
    service_name: str,
    environment: str = "local",
    debug: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        service_name: Name of the service (e.g., "embedding-generator")
        environment: Deployment environment (e.g., "local", "production")
        debug: Enable debug-level logging

    Example:
        >>> setup_logger("feature-store-api", environment="production", debug=False)
    """
    # Configure logging processors
    processors = [
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add log level
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add context variables (like request_id, user_id)
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Format as JSON for production, pretty-print for local dev
        structlog.processors.JSONRenderer() if environment != "local"
        else structlog.dev.ConsoleRenderer(colors=True)
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Create initial logger with context
    log = structlog.get_logger()
    log.info(
        "logger_initialized",
        service=service_name,
        environment=environment,
        debug=debug,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a logger instance with bound context.

    Args:
        name: Logger name (typically module name)

    Returns:
        structlog.BoundLogger: Configured logger

    Example:
        >>> log = get_logger(__name__)
        >>> log.info("processing_event", event_id="123", user_id="abc")
        {"event": "processing_event", "event_id": "123", "user_id": "abc", ...}

    Cost Tracking Example:
        >>> log = get_logger("embedding-generator")
        >>> log.info(
        ...     "embedding_generated",
        ...     tokens=150,
        ...     cache_hit=False,
        ...     cost_usd=0.0001,
        ...     latency_ms=45
        ... )
    """
    return structlog.get_logger(name)


class LogContext:
    """
    Context manager for adding temporary log context.

    This is useful for adding request-specific information that should
    appear in all logs within a request handler.

    Example:
        >>> log = get_logger(__name__)
        >>> with LogContext(request_id="req_123", user_id="user_456"):
        ...     log.info("processing_request")
        ...     # request_id and user_id will be in this log
        ...     process_data()
        ...     log.info("request_complete")
        ...     # request_id and user_id will be in this log too
    """

    def __init__(self, **context: Any):
        """
        Initialize log context.

        Args:
            **context: Key-value pairs to add to all logs
        """
        self.context = context

    def __enter__(self):
        """Enter context - bind variables to logger."""
        structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - unbind variables."""
        structlog.contextvars.unbind_contextvars(*self.context.keys())


def log_cost_metric(
    logger: structlog.BoundLogger,
    operation: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    latency_ms: float,
    cache_hit: bool = False,
    **extra_context: Any,
) -> None:
    """
    Log a cost-related metric.

    This creates structured logs that can be easily aggregated to track
    LLM API costs over time.

    Args:
        logger: Logger instance
        operation: Operation type (e.g., "embedding", "completion")
        model: Model name (e.g., "gpt-4")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost_usd: Cost in USD
        latency_ms: Latency in milliseconds
        cache_hit: Whether this was served from cache
        **extra_context: Additional context to log

    Example:
        >>> log = get_logger(__name__)
        >>> log_cost_metric(
        ...     log,
        ...     operation="embedding",
        ...     model="text-embedding-ada-002",
        ...     input_tokens=150,
        ...     output_tokens=0,
        ...     cost_usd=0.00015,
        ...     latency_ms=230,
        ...     cache_hit=False,
        ...     user_id="user_123"
        ... )

    These logs can be aggregated to answer questions like:
    - What's our daily LLM cost?
    - Which users are driving the most cost?
    - What's our cache hit rate?
    - Are we within our cost budget?
    """
    logger.info(
        "cost_metric",
        operation=operation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        cache_hit=cache_hit,
        # Calculate cost savings if cache hit
        cost_saved_usd=cost_usd if cache_hit else 0.0,
        timestamp=datetime.utcnow().isoformat(),
        **extra_context,
    )


def log_performance_metric(
    logger: structlog.BoundLogger,
    operation: str,
    duration_ms: float,
    success: bool = True,
    error: Optional[str] = None,
    **extra_context: Any,
) -> None:
    """
    Log a performance metric.

    Args:
        logger: Logger instance
        operation: Operation name (e.g., "feature_read", "drift_check")
        duration_ms: Operation duration in milliseconds
        success: Whether operation succeeded
        error: Error message if failed
        **extra_context: Additional context

    Example:
        >>> log = get_logger(__name__)
        >>> log_performance_metric(
        ...     log,
        ...     operation="feature_read",
        ...     duration_ms=12.5,
        ...     success=True,
        ...     feature_count=10
        ... )
    """
    logger.info(
        "performance_metric",
        operation=operation,
        duration_ms=duration_ms,
        success=success,
        error=error,
        timestamp=datetime.utcnow().isoformat(),
        **extra_context,
    )


# Example usage when running this module directly
if __name__ == "__main__":
    # Setup logger for testing
    setup_logger("test-service", environment="local", debug=True)

    # Get logger
    log = get_logger(__name__)

    # Basic logging
    log.info("test_event", message="This is a test")
    log.warning("test_warning", reason="Just testing")

    # Logging with context
    with LogContext(request_id="req_123", user_id="user_456"):
        log.info("processing_request")
        log.info("request_step", step="validation")
        log.info("request_complete")

    # Cost metric logging
    log_cost_metric(
        log,
        operation="embedding",
        model="all-MiniLM-L6-v2",
        input_tokens=150,
        output_tokens=0,
        cost_usd=0.0,  # Free!
        latency_ms=45.2,
        cache_hit=False,
    )

    # Performance metric logging
    log_performance_metric(
        log,
        operation="feature_read",
        duration_ms=12.5,
        success=True,
        feature_count=10,
    )

    print("\n✅ Logger test complete! Check the output above.")
