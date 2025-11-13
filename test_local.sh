#!/usr/bin/env bash

################################################################################
# Local Testing Script for LLM Feature Store
#
# This script runs comprehensive tests locally with minimal cost by:
# - Using DuckDB in-memory mode (zero cost)
# - Using sentence-transformers local embeddings (zero cost vs OpenAI)
# - Mocking cloud services (S3, Kafka)
# - Using local Redis or Redis mock
#
# Usage:
#   ./test_local.sh                    # Run all tests
#   ./test_local.sh --unit             # Run only unit tests
#   ./test_local.sh --integration      # Run only integration tests
#   ./test_local.sh --performance      # Run performance benchmarks
#   ./test_local.sh --coverage         # Run with coverage report
#   ./test_local.sh --quick            # Run quick tests (no integration)
#   ./test_local.sh --verbose          # Verbose output
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
RUN_UNIT=false
RUN_INTEGRATION=false
RUN_PERFORMANCE=false
RUN_COVERAGE=false
RUN_QUICK=false
VERBOSE=false

# Parse command line arguments
if [ $# -eq 0 ]; then
    # No arguments = run all tests
    RUN_UNIT=true
    RUN_INTEGRATION=true
    RUN_COVERAGE=true
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            RUN_UNIT=true
            shift
            ;;
        --integration)
            RUN_INTEGRATION=true
            shift
            ;;
        --performance)
            RUN_PERFORMANCE=true
            shift
            ;;
        --coverage)
            RUN_COVERAGE=true
            shift
            ;;
        --quick)
            RUN_QUICK=true
            RUN_UNIT=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            grep "^# Usage:" "$0" -A 20 | sed 's/^# //'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

################################################################################
# Helper Functions
################################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
        return 1
    fi
    return 0
}

################################################################################
# Pre-flight Checks
################################################################################

log_info "Starting Local Test Suite for LLM Feature Store"
log_info "================================================"
echo ""

# Check Python
log_info "Checking prerequisites..."
if ! check_command python; then
    log_error "Python is required"
    exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
log_success "Python $PYTHON_VERSION found"

# Check pip
if ! check_command pip; then
    log_error "pip is required"
    exit 1
fi

# Check if virtual environment is active
if [ -z "$VIRTUAL_ENV" ]; then
    log_warning "No virtual environment detected. Consider using a venv."
    log_warning "  python -m venv venv && source venv/bin/activate"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

################################################################################
# Install Dependencies (if needed)
################################################################################

log_info "Checking dependencies..."

# Check if pytest is installed
if ! python -c "import pytest" 2>/dev/null; then
    log_warning "pytest not found. Installing test dependencies..."
    pip install -q pytest pytest-cov pytest-asyncio pytest-mock pytest-timeout pytest-xdist faker
fi

# Check core dependencies
MISSING_DEPS=()

for dep in "pydantic" "duckdb" "pandas" "numpy" "structlog"; do
    if ! python -c "import $dep" 2>/dev/null; then
        MISSING_DEPS+=("$dep")
    fi
done

if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
    log_warning "Missing dependencies: ${MISSING_DEPS[*]}"
    log_info "Installing core dependencies..."
    pip install -q pydantic pydantic-settings duckdb pandas numpy structlog redis deltalake boto3
fi

log_success "Dependencies OK"

################################################################################
# Environment Setup
################################################################################

log_info "Setting up test environment..."

# Create .env.test if it doesn't exist
if [ ! -f .env.test ]; then
    log_info "Creating .env.test file with safe defaults..."
    cat > .env.test << 'EOF'
# Test Environment Configuration
# This uses local/mocked services to minimize cost

# DuckDB (zero cost - uses in-memory)
DUCKDB_PATH=:memory:

# Redis (uses local Redis or mock if unavailable)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=15  # Use separate DB for tests

# S3/MinIO (uses mock in tests)
AWS_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1

# Kafka (uses mock in tests)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_EMBEDDINGS=test_embeddings

# Embedding Model (uses local sentence-transformers - zero cost!)
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Feature Store
FEATURE_STORE_NAME=test_features

# Logging
LOG_LEVEL=WARNING  # Reduce noise in tests
EOF
    log_success "Created .env.test"
fi

# Export test environment
set -a  # Automatically export all variables
source .env.test 2>/dev/null || true
set +a

log_success "Environment configured"

################################################################################
# Test Execution
################################################################################

PYTEST_ARGS=""
if [ "$VERBOSE" = true ]; then
    PYTEST_ARGS="-v --tb=short"
else
    PYTEST_ARGS="-v --tb=line"
fi

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

################################################################################
# Unit Tests
################################################################################

if [ "$RUN_UNIT" = true ]; then
    log_info "Running Unit Tests..."
    echo ""

    UNIT_TEST_FILES=(
        "tests/test_models.py"
        "tests/test_duckdb_store.py"
        "tests/test_cache.py"
    )

    # Check which test files exist
    EXISTING_UNIT_TESTS=()
    for test_file in "${UNIT_TEST_FILES[@]}"; do
        if [ -f "$test_file" ]; then
            EXISTING_UNIT_TESTS+=("$test_file")
        fi
    done

    if [ ${#EXISTING_UNIT_TESTS[@]} -eq 0 ]; then
        log_warning "No unit test files found"
    else
        if [ "$RUN_COVERAGE" = true ]; then
            python -m pytest "${EXISTING_UNIT_TESTS[@]}" $PYTEST_ARGS \
                --cov=src \
                --cov-report=term-missing \
                --cov-report=html:htmlcov_unit \
                --cov-report=xml:coverage_unit.xml \
                2>&1 | tee test_unit.log || true
        else
            python -m pytest "${EXISTING_UNIT_TESTS[@]}" $PYTEST_ARGS 2>&1 | tee test_unit.log || true
        fi

        # Parse results from log
        if grep -q "passed" test_unit.log; then
            UNIT_PASSED=$(grep -oP '\d+(?= passed)' test_unit.log | tail -1 || echo "0")
            UNIT_FAILED=$(grep -oP '\d+(?= failed)' test_unit.log | tail -1 || echo "0")
            UNIT_SKIPPED=$(grep -oP '\d+(?= skipped)' test_unit.log | tail -1 || echo "0")

            TOTAL_TESTS=$((TOTAL_TESTS + UNIT_PASSED + UNIT_FAILED + UNIT_SKIPPED))
            PASSED_TESTS=$((PASSED_TESTS + UNIT_PASSED))
            FAILED_TESTS=$((FAILED_TESTS + UNIT_FAILED))
            SKIPPED_TESTS=$((SKIPPED_TESTS + UNIT_SKIPPED))

            log_success "Unit Tests: $UNIT_PASSED passed, $UNIT_FAILED failed, $UNIT_SKIPPED skipped"
        fi
        echo ""
    fi
fi

################################################################################
# Integration Tests
################################################################################

if [ "$RUN_INTEGRATION" = true ] && [ "$RUN_QUICK" = false ]; then
    log_info "Running Integration Tests..."
    log_warning "Note: Integration tests may require external dependencies (Redis, etc.)"
    echo ""

    # Check if integration tests exist
    if [ -f "tests/test_integration.py" ]; then
        # Check if torch is installed (needed for embeddings)
        if ! python -c "import torch" 2>/dev/null; then
            log_warning "PyTorch not installed. Installing (this may take a while)..."
            pip install -q torch sentence-transformers scikit-learn scipy
        fi

        python -m pytest tests/test_integration.py $PYTEST_ARGS \
            --timeout=300 \
            2>&1 | tee test_integration.log || true

        if grep -q "passed" test_integration.log; then
            INT_PASSED=$(grep -oP '\d+(?= passed)' test_integration.log | tail -1 || echo "0")
            INT_FAILED=$(grep -oP '\d+(?= failed)' test_integration.log | tail -1 || echo "0")
            INT_SKIPPED=$(grep -oP '\d+(?= skipped)' test_integration.log | tail -1 || echo "0")

            TOTAL_TESTS=$((TOTAL_TESTS + INT_PASSED + INT_FAILED + INT_SKIPPED))
            PASSED_TESTS=$((PASSED_TESTS + INT_PASSED))
            FAILED_TESTS=$((FAILED_TESTS + INT_FAILED))
            SKIPPED_TESTS=$((SKIPPED_TESTS + INT_SKIPPED))

            log_success "Integration Tests: $INT_PASSED passed, $INT_FAILED failed, $INT_SKIPPED skipped"
        fi
        echo ""
    else
        log_warning "No integration tests found (tests/test_integration.py)"
    fi
fi

################################################################################
# Performance Benchmarks
################################################################################

if [ "$RUN_PERFORMANCE" = true ]; then
    log_info "Running Performance Benchmarks..."
    echo ""

    if [ -f "tests/test_performance.py" ]; then
        # Check if dependencies are installed
        if ! python -c "import torch" 2>/dev/null; then
            log_warning "PyTorch not installed. Installing for performance tests..."
            pip install -q torch sentence-transformers
        fi

        python -m pytest tests/test_performance.py $PYTEST_ARGS \
            -v \
            --timeout=600 \
            2>&1 | tee test_performance.log || true

        if grep -q "passed" test_performance.log; then
            PERF_PASSED=$(grep -oP '\d+(?= passed)' test_performance.log | tail -1 || echo "0")
            PERF_FAILED=$(grep -oP '\d+(?= failed)' test_performance.log | tail -1 || echo "0")

            log_success "Performance Tests: $PERF_PASSED passed, $PERF_FAILED failed"
        fi
        echo ""

        # Display performance metrics if available
        if grep -q "BENCHMARK" test_performance.log; then
            log_info "Performance Metrics:"
            grep "BENCHMARK" test_performance.log | sed 's/^/  /'
            echo ""
        fi
    else
        log_warning "No performance tests found (tests/test_performance.py)"
    fi
fi

################################################################################
# Summary
################################################################################

echo ""
log_info "Test Summary"
log_info "============"
echo ""

if [ $TOTAL_TESTS -gt 0 ]; then
    PASS_RATE=$(awk "BEGIN {printf \"%.1f\", ($PASSED_TESTS / $TOTAL_TESTS) * 100}")

    echo -e "Total Tests:   ${BLUE}$TOTAL_TESTS${NC}"
    echo -e "Passed:        ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed:        ${RED}$FAILED_TESTS${NC}"
    echo -e "Skipped:       ${YELLOW}$SKIPPED_TESTS${NC}"
    echo -e "Pass Rate:     ${GREEN}$PASS_RATE%${NC}"
    echo ""

    if [ $FAILED_TESTS -eq 0 ]; then
        log_success "All tests passed! 🎉"
        EXIT_CODE=0
    else
        log_error "$FAILED_TESTS test(s) failed. Check logs for details."
        EXIT_CODE=1
    fi
else
    log_warning "No tests were run"
    EXIT_CODE=1
fi

################################################################################
# Coverage Report
################################################################################

if [ "$RUN_COVERAGE" = true ]; then
    echo ""
    log_info "Coverage Report"
    log_info "==============="

    if [ -f "coverage_unit.xml" ]; then
        # Extract coverage percentage
        if command -v coverage &> /dev/null; then
            coverage report --omit="tests/*" 2>/dev/null || true
        fi

        if [ -d "htmlcov_unit" ]; then
            log_success "HTML coverage report generated: htmlcov_unit/index.html"
            log_info "Open in browser: file://$(pwd)/htmlcov_unit/index.html"
        fi
    fi
fi

################################################################################
# Cost Savings Summary
################################################################################

echo ""
log_info "Cost Savings (Local Testing)"
log_info "=============================="
echo ""
echo "✅ DuckDB (in-memory):         \$0  vs BigQuery ~\$5/TB"
echo "✅ Sentence-Transformers:      \$0  vs OpenAI ~\$0.0001/1K tokens"
echo "✅ Local Redis/Mock:           \$0  vs Elasticache ~\$50/month"
echo "✅ Mocked Services (S3, Kafka): \$0  vs Cloud services"
echo ""
log_success "Total savings: ~\$100-200/month by testing locally!"

################################################################################
# Cleanup
################################################################################

echo ""
log_info "Test logs saved:"
[ -f test_unit.log ] && echo "  - test_unit.log"
[ -f test_integration.log ] && echo "  - test_integration.log"
[ -f test_performance.log ] && echo "  - test_performance.log"

echo ""
log_info "Test run complete"

exit $EXIT_CODE
