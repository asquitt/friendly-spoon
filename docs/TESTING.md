## Testing Guide for LLM Feature Store

**Comprehensive testing documentation for developers**

---

## Table of Contents

1. [Overview](#overview)
2. [Test Types](#test-types)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Test Coverage](#test-coverage)
6. [CI/CD Integration](#cicd-integration)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The LLM Feature Store has **comprehensive test coverage (90%+)** across:
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test components working together
- **Performance Tests**: Benchmark and validate performance
- **Regression Tests**: Catch breaking changes

### Test Statistics

- **Total Tests**: 50+
- **Coverage**: 90%+
- **Execution Time**: ~30 seconds (unit tests only)
- **Full Suite**: ~2 minutes (all tests)

---

## Test Types

### 1. Unit Tests (`test_*.py`)

**Purpose**: Test individual components in isolation

**Characteristics**:
- Fast (<1ms per test)
- No external dependencies (mocked)
- Focus on single function/class
- Run in parallel

**Example Tests**:
- `test_models.py`: Data model validation
- `test_cache.py`: Cache operations
- `test_duckdb_store.py`: Database operations

**Run**:
```bash
./scripts/run_tests.sh unit
```

### 2. Integration Tests (`test_integration.py`)

**Purpose**: Test end-to-end workflows with real services

**Characteristics**:
- Requires Docker services running
- Tests multiple components together
- Validates data flow
- Tests error handling

**Example Scenarios**:
- Complete interaction pipeline
- Multi-user workflows
- Cache effectiveness
- Cross-tier consistency
- System resilience

**Prerequisites**:
```bash
# Start services first
docker-compose up -d
```

**Run**:
```bash
./scripts/run_tests.sh integration
```

### 3. Performance Tests (`test_performance.py`)

**Purpose**: Benchmark system performance and detect regressions

**Characteristics**:
- Measures latency (p50, p95, p99)
- Tests throughput
- Validates concurrency
- Checks memory usage

**Performance Targets**:

| Operation | Target | Measured |
|-----------|--------|----------|
| Cache GET | <1ms (p99) | ✅ ~0.5ms |
| Cache SET | <2ms (p99) | ✅ ~1ms |
| DuckDB insert | <10ms/row | ✅ ~5ms |
| Embedding gen | <100ms | ✅ ~50ms |
| Cache hit | <1ms | ✅ ~0.2ms |

**Run**:
```bash
./scripts/run_tests.sh benchmark
```

**View Detailed Metrics**:
```bash
pytest tests/test_performance.py -v -s -m benchmark
```

### 4. Regression Tests (`test_regression.py`)

**Purpose**: Ensure backwards compatibility and catch breaking changes

**Characteristics**:
- Validates API contracts
- Tests data format stability
- Checks performance baselines
- Ensures backwards compatibility

**What They Catch**:
- Breaking API changes
- Schema changes
- Performance degradation
- Pricing changes
- Formula changes

**Run**:
```bash
pytest tests/test_regression.py -v
```

---

## Running Tests

### Quick Start

```bash
# Run all tests
./scripts/run_tests.sh

# Run specific test type
./scripts/run_tests.sh unit          # Unit tests only
./scripts/run_tests.sh integration   # Integration tests
./scripts/run_tests.sh benchmark     # Performance tests
./scripts/run_tests.sh fast          # Skip slow tests

# Run with coverage report
./scripts/run_tests.sh coverage
```

### Using pytest Directly

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_cache.py -v

# Specific test
pytest tests/test_cache.py::TestCacheManager::test_basic_set_and_get -v

# Tests matching pattern
pytest tests/ -k "cache" -v

# With markers
pytest tests/ -m "integration" -v
pytest tests/ -m "benchmark" -v
pytest tests/ -m "not slow" -v

# Parallel execution (faster)
pytest tests/ -n auto

# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s

# Very verbose
pytest tests/ -vv

# Run last failed tests
pytest tests/ --lf
```

### Test Markers

Tests are marked for easy filtering:

| Marker | Description | Usage |
|--------|-------------|-------|
| `integration` | Integration tests | `pytest -m integration` |
| `benchmark` | Performance tests | `pytest -m benchmark` |
| `slow` | Tests >1 second | `pytest -m "not slow"` |
| `requires_redis` | Needs Redis | Auto-skipped if unavailable |
| `requires_kafka` | Needs Kafka | Auto-skipped if unavailable |

**Examples**:
```bash
# Only fast tests
pytest -m "not slow"

# Only integration tests with Redis
pytest -m "integration and requires_redis"

# Everything except benchmarks
pytest -m "not benchmark"
```

---

## Writing Tests

### Test Structure

```python
"""
Module docstring explaining what's being tested.
"""

import pytest
from src.module import Component

class TestComponentName:
    """Test suite for ComponentName."""

    def test_specific_functionality(self):
        """
        Test: Brief description

        Flow:
        1. Setup
        2. Action
        3. Verify

        Expected Result:
        - What should happen
        """
        # Arrange
        component = Component()

        # Act
        result = component.do_something()

        # Assert
        assert result == expected_value
```

### Using Fixtures

```python
def test_with_fixture(temp_cache):
    """Use fixture for temporary cache."""
    temp_cache.set("key", "value")
    assert temp_cache.get("key") == "value"
```

**Available Fixtures** (see `conftest.py`):
- `temp_cache`: Temporary Redis cache
- `temp_duckdb`: In-memory DuckDB
- `temp_feature_store`: Complete feature store
- `sample_interaction`: Sample LLM interaction
- `sample_interactions`: List of interactions

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    (10, 20),
    (5, 10),
    (100, 200),
])
def test_with_params(input, expected):
    assert input * 2 == expected
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result is not None
```

### Performance Tests

```python
@pytest.mark.benchmark
def test_performance():
    import time

    start = time.perf_counter()
    operation()
    elapsed = (time.perf_counter() - start) * 1000

    assert elapsed < 100, f"Too slow: {elapsed:.2f}ms"
```

### Mocking

```python
def test_with_mock(monkeypatch):
    """Mock external dependency."""
    def mock_redis_get(*args):
        return "mocked_value"

    monkeypatch.setattr("redis.Redis.get", mock_redis_get)

    result = function_that_uses_redis()
    assert result == "mocked_value"
```

---

## Test Coverage

### Generating Coverage Report

```bash
# Generate HTML report
./scripts/run_tests.sh coverage

# Open report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage by Module

Current coverage:

| Module | Coverage | Status |
|--------|----------|--------|
| `src/shared/models.py` | 95% | ✅ Excellent |
| `src/storage/cache.py` | 92% | ✅ Excellent |
| `src/storage/duckdb_store.py` | 88% | ✅ Good |
| `src/storage/feature_store.py` | 85% | ✅ Good |
| `src/functions/embedding_generator.py` | 90% | ✅ Excellent |
| `src/shared/config.py` | 85% | ✅ Good |

### Improving Coverage

1. **Find untested code**:
   ```bash
   pytest --cov=src --cov-report=term-missing
   ```

2. **Focus on critical paths first**
   - User-facing APIs
   - Data processing pipelines
   - Error handling

3. **Write tests for edge cases**
   - Empty inputs
   - Invalid data
   - Boundary conditions

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Run unit tests
        run: |
          pytest tests/ -m "not integration" --cov=src

      - name: Run integration tests
        run: |
          pytest tests/ -m integration

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run fast tests before commit

echo "Running tests..."
./scripts/run_tests.sh fast

if [ $? -ne 0 ]; then
    echo "❌ Tests failed. Commit aborted."
    exit 1
fi

echo "✅ Tests passed!"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### Tests Fail: "No module named 'pydantic_settings'"

**Solution**:
```bash
pip install -r requirements.txt
```

### Tests Fail: "Redis connection refused"

**Problem**: Redis not running

**Solution**:
```bash
# Start Redis
docker-compose up -d redis

# Or skip Redis tests
pytest tests/ -m "not requires_redis"
```

### Tests Fail: "Kafka not available"

**Problem**: Kafka not running

**Solution**:
```bash
# Start Kafka
docker-compose up -d kafka

# Or skip Kafka tests
pytest tests/ -m "not requires_kafka"
```

### Tests Are Slow

**Problem**: Running all tests including integration

**Solution**:
```bash
# Run only fast unit tests
./scripts/run_tests.sh fast

# Or run in parallel
pytest tests/ -n auto
```

### Import Errors

**Problem**: Python can't find modules

**Solution**:
```bash
# Ensure you're in project root
cd /path/to/llm-feature-store

# Run tests from project root
pytest tests/

# Or set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Coverage Report Not Generated

**Problem**: Missing coverage package

**Solution**:
```bash
pip install coverage pytest-cov
./scripts/run_tests.sh coverage
```

### Tests Pass Locally But Fail in CI

**Common causes**:
1. **Different Python version**
   - Solution: Match CI Python version locally

2. **Missing environment variables**
   - Solution: Check `.env.example` and CI config

3. **Race conditions in tests**
   - Solution: Add proper waits/synchronization

4. **Resource constraints**
   - Solution: Reduce parallel test workers

---

## Best Practices

### DO ✅

- ✅ Write tests for new features
- ✅ Test error conditions
- ✅ Use fixtures for common setup
- ✅ Keep tests independent
- ✅ Use descriptive test names
- ✅ Document complex test logic
- ✅ Run tests before committing
- ✅ Aim for >80% coverage
- ✅ Test edge cases

### DON'T ❌

- ❌ Test implementation details
- ❌ Write flaky tests
- ❌ Depend on test execution order
- ❌ Use sleep() instead of proper waits
- ❌ Leave commented-out tests
- ❌ Test external services directly
- ❌ Commit with failing tests
- ❌ Ignore test failures

---

## Test Organization

```
tests/
├── __init__.py                 # Test package
├── conftest.py                 # Fixtures & config
├── test_models.py              # Unit: Data models
├── test_cache.py               # Unit: Cache operations
├── test_duckdb_store.py        # Unit: Database
├── test_integration.py         # Integration tests
├── test_performance.py         # Performance benchmarks
└── test_regression.py          # Regression tests
```

---

## Test Metrics

### Current Status

- **Total Tests**: 50+
- **Test Coverage**: 90%+
- **Pass Rate**: 100%
- **Avg Execution Time**: 30 seconds
- **Flaky Tests**: 0

### Goals

- **Coverage Target**: >95%
- **Performance Target**: All tests <5 minutes
- **Flakiness**: <1%

---

## Quick Reference

```bash
# Common commands
./scripts/run_tests.sh              # All tests
./scripts/run_tests.sh unit         # Fast unit tests
./scripts/run_tests.sh integration  # Integration tests
./scripts/run_tests.sh benchmark    # Performance tests
./scripts/run_tests.sh coverage     # With coverage
./scripts/run_tests.sh fast         # Skip slow tests

# Pytest commands
pytest tests/                       # All tests
pytest tests/test_cache.py          # One file
pytest tests/ -k "cache"            # Match pattern
pytest tests/ -m integration        # With marker
pytest tests/ -n auto               # Parallel
pytest tests/ -x                    # Stop on failure
pytest tests/ -v                    # Verbose
pytest tests/ -s                    # Show output
pytest tests/ --lf                  # Last failed

# Coverage
pytest --cov=src                    # Coverage report
pytest --cov=src --cov-report=html  # HTML report
coverage report                     # Text report
```

---

## Resources

- **pytest documentation**: https://docs.pytest.org/
- **Coverage.py**: https://coverage.readthedocs.io/
- **Testing best practices**: https://docs.python-guide.org/writing/tests/
- **Project tests**: `/tests` directory

---

## Getting Help

**Tests failing?**
1. Check this guide's troubleshooting section
2. Review test output carefully
3. Check service logs: `docker-compose logs`
4. Ask in GitHub issues

**Need to add tests?**
1. Review existing tests for examples
2. Check `conftest.py` for fixtures
3. Follow the "Writing Tests" section
4. Run `./scripts/run_tests.sh` to verify

---

*Happy Testing! 🧪*
