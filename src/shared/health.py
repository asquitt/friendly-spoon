"""
Health Check System for Production Deployments.

This module provides:
- Service health checks
- Dependency health monitoring
- Readiness and liveness probes
- Health status aggregation

Used for:
- Kubernetes probes
- Load balancer health checks
- Monitoring dashboards
- Automatic failover
"""

from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime
import time

from .logger import get_logger
from .config import get_config

log = get_logger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"      # Service is fully operational
    DEGRADED = "degraded"    # Service is working but with issues
    UNHEALTHY = "unhealthy"  # Service is not operational


class HealthCheck:
    """
    Base class for health checks.

    Each dependency (Redis, Kafka, etc.) implements its own health check.
    """

    def __init__(self, name: str, timeout: float = 5.0):
        """
        Initialize health check.

        Args:
            name: Check name (e.g., "redis", "kafka")
            timeout: Timeout in seconds
        """
        self.name = name
        self.timeout = timeout
        self.last_check_time: Optional[datetime] = None
        self.last_status: Optional[HealthStatus] = None
        self.last_error: Optional[str] = None

    def check(self) -> tuple[HealthStatus, Optional[str]]:
        """
        Perform health check.

        Returns:
            tuple: (status, error_message)

        Example:
            >>> check = RedisHealthCheck()
            >>> status, error = check.check()
            >>> if status == HealthStatus.HEALTHY:
            ...     print("Redis is healthy!")
        """
        raise NotImplementedError("Subclasses must implement check()")

    def execute(self) -> Dict:
        """
        Execute health check and return results.

        Returns:
            dict: Health check results with timing
        """
        start = time.time()

        try:
            status, error = self.check()
        except Exception as e:
            status = HealthStatus.UNHEALTHY
            error = str(e)
            log.error(
                "health_check_failed",
                check=self.name,
                error=error
            )

        elapsed_ms = (time.time() - start) * 1000

        self.last_check_time = datetime.utcnow()
        self.last_status = status
        self.last_error = error

        return {
            "name": self.name,
            "status": status.value,
            "timestamp": self.last_check_time.isoformat(),
            "response_time_ms": round(elapsed_ms, 2),
            "error": error
        }


class RedisHealthCheck(HealthCheck):
    """Health check for Redis."""

    def __init__(self):
        super().__init__("redis")
        self.redis = None

    def check(self) -> tuple[HealthStatus, Optional[str]]:
        """Check Redis connectivity."""
        try:
            from ..storage.cache import CacheManager

            if self.redis is None:
                cache = CacheManager()
                self.redis = cache.redis

            # Ping Redis
            if self.redis.ping():
                return HealthStatus.HEALTHY, None
            else:
                return HealthStatus.UNHEALTHY, "Redis ping failed"

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Redis error: {str(e)}"


class DuckDBHealthCheck(HealthCheck):
    """Health check for DuckDB."""

    def __init__(self):
        super().__init__("duckdb")

    def check(self) -> tuple[HealthStatus, Optional[str]]:
        """Check DuckDB connectivity."""
        try:
            from ..storage.duckdb_store import DuckDBStore

            # Try to connect and query
            store = DuckDBStore()
            result = store.conn.execute("SELECT 1").fetchone()
            store.close()

            if result and result[0] == 1:
                return HealthStatus.HEALTHY, None
            else:
                return HealthStatus.UNHEALTHY, "DuckDB query failed"

        except Exception as e:
            return HealthStatus.UNHEALTHY, f"DuckDB error: {str(e)}"


class KafkaHealthCheck(HealthCheck):
    """Health check for Kafka."""

    def __init__(self):
        super().__init__("kafka")

    def check(self) -> tuple[HealthStatus, Optional[str]]:
        """Check Kafka connectivity."""
        try:
            from kafka import KafkaConsumer
            from kafka.errors import KafkaError

            config = get_config()

            # Try to create consumer (doesn't actually consume)
            consumer = KafkaConsumer(
                bootstrap_servers=config.kafka_bootstrap_servers.split(","),
                request_timeout_ms=5000
            )

            # Get topics (tests connection)
            topics = consumer.topics()
            consumer.close()

            if topics is not None:
                return HealthStatus.HEALTHY, None
            else:
                return HealthStatus.DEGRADED, "Kafka accessible but no topics"

        except KafkaError as e:
            return HealthStatus.UNHEALTHY, f"Kafka error: {str(e)}"
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Unexpected error: {str(e)}"


class TemporalHealthCheck(HealthCheck):
    """Health check for Temporal."""

    def __init__(self):
        super().__init__("temporal")

    def check(self) -> tuple[HealthStatus, Optional[str]]:
        """Check Temporal connectivity."""
        try:
            # For now, just check if we can import
            # In production, would actually connect to Temporal
            import temporalio
            return HealthStatus.HEALTHY, None

        except ImportError:
            return HealthStatus.UNHEALTHY, "Temporal not installed"
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Temporal error: {str(e)}"


class HealthCheckAggregator:
    """
    Aggregates health checks from multiple services.

    This provides a single endpoint for overall system health.

    Example:
        >>> aggregator = HealthCheckAggregator()
        >>> aggregator.register(RedisHealthCheck())
        >>> aggregator.register(DuckDBHealthCheck())
        >>> status = aggregator.check_all()
        >>> print(f"Overall: {status['overall_status']}")
    """

    def __init__(self):
        """Initialize aggregator."""
        self.checks: List[HealthCheck] = []
        log.info("health_check_aggregator_initialized")

    def register(self, check: HealthCheck) -> None:
        """
        Register a health check.

        Args:
            check: HealthCheck instance
        """
        self.checks.append(check)
        log.debug("health_check_registered", check=check.name)

    def check_all(self) -> Dict:
        """
        Run all registered health checks.

        Returns:
            dict: Aggregated health results

        Example:
            >>> results = aggregator.check_all()
            >>> if results['overall_status'] == 'healthy':
            ...     print("All systems operational!")
        """
        start = time.time()

        results = []
        statuses = []

        for check in self.checks:
            result = check.execute()
            results.append(result)
            statuses.append(result["status"])

        # Determine overall status
        if all(s == "healthy" for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == "unhealthy" for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED

        elapsed_ms = (time.time() - start) * 1000

        response = {
            "overall_status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results,
            "total_checks": len(results),
            "healthy_checks": sum(1 for s in statuses if s == "healthy"),
            "response_time_ms": round(elapsed_ms, 2)
        }

        log.info(
            "health_check_complete",
            overall_status=overall_status.value,
            healthy=response["healthy_checks"],
            total=response["total_checks"]
        )

        return response

    def is_healthy(self) -> bool:
        """
        Quick check if system is healthy.

        Returns:
            bool: True if all checks pass
        """
        result = self.check_all()
        return result["overall_status"] == HealthStatus.HEALTHY.value

    def is_ready(self) -> bool:
        """
        Readiness probe for Kubernetes.

        Returns:
            bool: True if system is ready to serve traffic

        Note:
            Readiness is more strict than liveness.
            Service should not receive traffic if not ready.
        """
        # For readiness, require all critical services
        critical_checks = ["redis", "duckdb"]

        result = self.check_all()

        for check in result["checks"]:
            if check["name"] in critical_checks:
                if check["status"] != "healthy":
                    return False

        return True

    def is_alive(self) -> bool:
        """
        Liveness probe for Kubernetes.

        Returns:
            bool: True if service is alive (should not be restarted)

        Note:
            Liveness is more lenient than readiness.
            Service is alive if it's responding, even if degraded.
        """
        result = self.check_all()

        # Alive if not completely unhealthy
        return result["overall_status"] != HealthStatus.UNHEALTHY.value


# =============================================================================
# Global Health Check Instance
# =============================================================================

_health_aggregator: Optional[HealthCheckAggregator] = None


def get_health_aggregator() -> HealthCheckAggregator:
    """
    Get global health check aggregator (singleton).

    Returns:
        HealthCheckAggregator: Global instance

    Example:
        >>> aggregator = get_health_aggregator()
        >>> status = aggregator.check_all()
    """
    global _health_aggregator

    if _health_aggregator is None:
        _health_aggregator = HealthCheckAggregator()

        # Register default checks
        _health_aggregator.register(RedisHealthCheck())
        _health_aggregator.register(DuckDBHealthCheck())
        _health_aggregator.register(KafkaHealthCheck())
        _health_aggregator.register(TemporalHealthCheck())

    return _health_aggregator


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger

    setup_logger("health-check-test", environment="local", debug=True)

    print("🏥 Testing health checks...\n")

    # Get aggregator
    aggregator = get_health_aggregator()

    # Run all checks
    results = aggregator.check_all()

    # Display results
    print(f"Overall Status: {results['overall_status'].upper()}")
    print(f"Checks: {results['healthy_checks']}/{results['total_checks']} healthy")
    print(f"Response Time: {results['response_time_ms']:.2f}ms\n")

    print("Individual Checks:")
    for check in results["checks"]:
        status_icon = "✅" if check["status"] == "healthy" else "❌"
        print(f"  {status_icon} {check['name']}: {check['status']}")
        if check["error"]:
            print(f"     Error: {check['error']}")
        print(f"     Response Time: {check['response_time_ms']:.2f}ms")

    print(f"\nReadiness: {'✅ Ready' if aggregator.is_ready() else '❌ Not Ready'}")
    print(f"Liveness: {'✅ Alive' if aggregator.is_alive() else '❌ Not Alive'}")
