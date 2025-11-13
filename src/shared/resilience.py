"""
Resilience Patterns for Production Systems.

This module provides:
- Circuit breakers (prevent cascading failures)
- Retry logic with exponential backoff
- Timeout handlers
- Bulkheads (resource isolation)
- Rate limiting

These patterns make the system resilient to:
- Service outages
- Network issues
- Overload conditions
- Cascading failures
"""

import time
import functools
from enum import Enum
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
import threading

from .logger import get_logger

log = get_logger(__name__)


# =============================================================================
# Circuit Breaker Pattern
# =============================================================================

class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    The circuit breaker has three states:
    1. CLOSED: Normal operation, requests pass through
    2. OPEN: Too many failures, reject requests immediately
    3. HALF_OPEN: Testing if service recovered

    State transitions:
    - CLOSED → OPEN: After failure_threshold failures
    - OPEN → HALF_OPEN: After recovery_timeout seconds
    - HALF_OPEN → CLOSED: After success_threshold successes
    - HALF_OPEN → OPEN: On any failure

    Example:
        >>> breaker = CircuitBreaker("redis", failure_threshold=5)
        >>> @breaker.protect
        ... def call_redis():
        ...     return redis.get("key")
        >>> result = call_redis()  # Auto-protected by circuit breaker
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name (for logging)
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before half-open
            success_threshold: Successes needed to close from half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None

        self.lock = threading.Lock()

        log.info(
            "circuit_breaker_initialized",
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function return value

        Raises:
            CircuitBreakerError: If circuit is open
        """
        with self.lock:
            # Check if we should attempt recovery
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )

        try:
            # Call function
            result = func(*args, **kwargs)

            # Record success
            with self.lock:
                self._on_success()

            return result

        except Exception as e:
            # Record failure
            with self.lock:
                self._on_failure()

            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0

        log.info(
            "circuit_breaker_half_open",
            name=self.name
        )

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1

            if self.success_count >= self.success_threshold:
                self._transition_to_closed()

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            # Immediately open on failure in half-open
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1

            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0

        log.info(
            "circuit_breaker_closed",
            name=self.name
        )

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        self.state = CircuitState.OPEN
        self.failure_count = 0

        log.warning(
            "circuit_breaker_open",
            name=self.name
        )

    def protect(self, func: Callable) -> Callable:
        """
        Decorator to protect a function with circuit breaker.

        Example:
            >>> breaker = CircuitBreaker("my_service")
            >>> @breaker.protect
            ... def call_service():
            ...     return service.call()
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)

        return wrapper

    def get_state(self) -> Dict:
        """
        Get current circuit breaker state.

        Returns:
            dict: State information
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


# =============================================================================
# Retry Pattern
# =============================================================================

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        exceptions: Tuple of exceptions to catch

    Example:
        >>> @retry_with_backoff(max_retries=3, initial_delay=1.0)
        ... def flaky_operation():
        ...     response = requests.get("https://api.example.com")
        ...     return response.json()

    Backoff schedule:
    - Attempt 1: 0s (immediate)
    - Attempt 2: 1s delay
    - Attempt 3: 2s delay
    - Attempt 4: 4s delay
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    if attempt == max_retries:
                        # Last attempt failed, raise exception
                        log.error(
                            "retry_exhausted",
                            func=func.__name__,
                            attempts=attempt + 1,
                            error=str(e)
                        )
                        raise

                    # Calculate next delay
                    actual_delay = min(delay, max_delay)

                    log.warning(
                        "retry_attempt",
                        func=func.__name__,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=actual_delay,
                        error=str(e)
                    )

                    # Wait before retry
                    time.sleep(actual_delay)

                    # Exponential backoff
                    delay *= exponential_base

        return wrapper
    return decorator


# =============================================================================
# Timeout Pattern
# =============================================================================

def timeout(seconds: float):
    """
    Decorator to add timeout to function.

    Args:
        seconds: Timeout in seconds

    Example:
        >>> @timeout(5.0)
        ... def slow_operation():
        ...     time.sleep(10)  # Will timeout after 5s

    Note:
        This uses threading and may not work for all operations.
        For I/O operations, consider using native timeouts.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)

            if thread.is_alive():
                log.error(
                    "operation_timeout",
                    func=func.__name__,
                    timeout=seconds
                )
                raise TimeoutError(
                    f"Operation '{func.__name__}' timed out after {seconds}s"
                )

            if exception[0]:
                raise exception[0]

            return result[0]

        return wrapper
    return decorator


# =============================================================================
# Rate Limiter
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter.

    Limits the rate of operations using token bucket algorithm.

    Example:
        >>> limiter = RateLimiter(rate=10, capacity=20)  # 10 ops/sec, burst 20
        >>> @limiter.limit
        ... def expensive_operation():
        ...     return api.call()
    """

    def __init__(self, rate: float, capacity: int):
        """
        Initialize rate limiter.

        Args:
            rate: Tokens added per second
            capacity: Maximum token capacity (burst size)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            bool: True if acquired, False if rate limited
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add new tokens
            self.tokens = min(
                self.capacity,
                self.tokens + (elapsed * self.rate)
            )

            self.last_update = now

            # Try to acquire
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def limit(self, func: Callable) -> Callable:
        """
        Decorator to rate limit function.

        Example:
            >>> limiter = RateLimiter(rate=10, capacity=20)
            >>> @limiter.limit
            ... def api_call():
            ...     return requests.get("https://api.example.com")
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.acquire():
                raise RateLimitError("Rate limit exceeded")

            return func(*args, **kwargs)

        return wrapper


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    pass


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from ..shared.logger import setup_logger

    setup_logger("resilience-test", environment="local", debug=True)

    print("🛡️  Testing resilience patterns...\n")

    # Test circuit breaker
    print("1. Circuit Breaker")
    breaker = CircuitBreaker("test_service", failure_threshold=3)

    @breaker.protect
    def unstable_service(should_fail: bool = False):
        if should_fail:
            raise Exception("Service failure")
        return "Success"

    # Should work initially
    try:
        print(f"   Call 1: {unstable_service()}")
    except:
        pass

    # Fail multiple times to open circuit
    for i in range(5):
        try:
            unstable_service(should_fail=True)
        except:
            print(f"   Call {i+2}: Failed")

    # Circuit should be open now
    try:
        unstable_service()
    except CircuitBreakerError:
        print("   Circuit breaker is OPEN (protecting service)")

    # Test retry
    print("\n2. Retry with Backoff")

    attempt_count = [0]

    @retry_with_backoff(max_retries=3, initial_delay=0.5)
    def flaky_operation():
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise Exception("Temporary failure")
        return "Success"

    try:
        result = flaky_operation()
        print(f"   Result: {result} (after {attempt_count[0]} attempts)")
    except:
        print("   Failed after all retries")

    # Test rate limiter
    print("\n3. Rate Limiter")
    limiter = RateLimiter(rate=2, capacity=5)  # 2 per second, burst 5

    @limiter.limit
    def rate_limited_operation():
        return "Success"

    # Should work for first 5 (burst)
    for i in range(7):
        try:
            rate_limited_operation()
            print(f"   Call {i+1}: Success")
        except RateLimitError:
            print(f"   Call {i+1}: Rate limited")

    print("\n✅ Resilience patterns test complete!")
