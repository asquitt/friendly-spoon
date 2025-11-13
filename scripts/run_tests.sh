#!/bin/bash
# Run comprehensive test suite
#
# Usage:
#   ./scripts/run_tests.sh              # Run all tests
#   ./scripts/run_tests.sh unit         # Run only unit tests
#   ./scripts/run_tests.sh integration  # Run only integration tests
#   ./scripts/run_tests.sh coverage     # Run with coverage report

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}LLM Feature Store - Test Runner${NC}"
echo -e "${GREEN}================================${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "Activating venv..."
    source venv/bin/activate 2>/dev/null || {
        echo -e "${RED}❌ Could not activate venv${NC}"
        echo "Run: source venv/bin/activate"
        exit 1
    }
fi

# Ensure pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}❌ pytest not found${NC}"
    echo "Installing test dependencies..."
    pip install pytest pytest-cov pytest-asyncio
fi

# Parse test type
TEST_TYPE=${1:-all}

case $TEST_TYPE in
    unit)
        echo -e "${GREEN}📝 Running unit tests only...${NC}"
        pytest tests/ -v -m "not integration and not benchmark" --tb=short
        ;;

    integration)
        echo -e "${GREEN}🔗 Running integration tests...${NC}"
        echo -e "${YELLOW}Note: Requires Redis and Kafka to be running${NC}"
        pytest tests/ -v -m "integration" --tb=short
        ;;

    benchmark)
        echo -e "${GREEN}⏱️  Running performance benchmarks...${NC}"
        pytest tests/ -v -m "benchmark" --tb=short
        ;;

    coverage)
        echo -e "${GREEN}📊 Running tests with coverage...${NC}"
        pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html
        echo ""
        echo -e "${GREEN}✅ Coverage report generated${NC}"
        echo "Open htmlcov/index.html to view detailed report"
        ;;

    fast)
        echo -e "${GREEN}⚡ Running fast tests only...${NC}"
        pytest tests/ -v -m "not slow and not integration and not benchmark" --tb=short
        ;;

    all)
        echo -e "${GREEN}🧪 Running all tests...${NC}"
        pytest tests/ -v --tb=short
        ;;

    *)
        echo -e "${RED}❌ Unknown test type: $TEST_TYPE${NC}"
        echo ""
        echo "Usage:"
        echo "  ./scripts/run_tests.sh [unit|integration|benchmark|coverage|fast|all]"
        echo ""
        echo "Examples:"
        echo "  ./scripts/run_tests.sh              # Run all tests"
        echo "  ./scripts/run_tests.sh unit         # Unit tests only"
        echo "  ./scripts/run_tests.sh coverage     # With coverage report"
        exit 1
        ;;
esac

TEST_EXIT_CODE=$?

echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo -e "${GREEN}================================${NC}"
else
    echo -e "${RED}================================${NC}"
    echo -e "${RED}❌ Some tests failed${NC}"
    echo -e "${RED}================================${NC}"
    exit $TEST_EXIT_CODE
fi

# Display test summary
echo ""
echo "Test Summary:"
echo "  Type: $TEST_TYPE"
echo "  Exit Code: $TEST_EXIT_CODE"

# If coverage was run, show coverage summary
if [ "$TEST_TYPE" = "coverage" ]; then
    echo ""
    echo "Coverage Summary:"
    coverage report --skip-empty | tail -n 3
fi

echo ""
echo "💡 Tips:"
echo "  • Run 'pytest tests/test_specific.py' to test one file"
echo "  • Use '-k test_name' to run specific tests"
echo "  • Add '-vv' for more verbose output"
echo "  • Use '--pdb' to debug on failure"
