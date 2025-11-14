#!/usr/bin/env bash
################################################################################
# Progress Checker for LLM Feature Store Learning Path
#
# This script checks your progress through the learning path by running tests
# and counting completed exercises.
#
# Usage:
#   ./scripts/check-progress.sh
#   ./scripts/check-progress.sh --week 1
#   ./scripts/check-progress.sh --summary
################################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Progress indicators
COMPLETED="✅"
IN_PROGRESS="🔄"
NOT_STARTED="⏳"

# Base directory
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

check_week_tests() {
    local week=$1
    local week_dir="${BASE_DIR}/week-${week}"

    if [ ! -d "$week_dir" ]; then
        echo "NOT_STARTED"
        return
    fi

    # Run tests for this week
    if [ -d "${week_dir}/tests" ]; then
        cd "$BASE_DIR"
        if python -m pytest "${week_dir}/tests" -q > /dev/null 2>&1; then
            echo "COMPLETED"
        else
            echo "IN_PROGRESS"
        fi
    else
        echo "NOT_STARTED"
    fi
}

count_completed_exercises() {
    local week=$1
    local week_dir="${BASE_DIR}/week-${week}"

    if [ ! -d "${week_dir}/exercises" ]; then
        echo "0/0"
        return
    fi

    # Count exercise files
    local total=$(find "${week_dir}/exercises" -name "*.py" -type f 2>/dev/null | wc -l)
    local completed=$(find "${week_dir}/solutions" -name "*.py" -type f 2>/dev/null | wc -l)

    echo "${completed}/${total}"
}

################################################################################
# Main Progress Check
################################################################################

print_header "LLM Feature Store - Learning Progress"
echo ""

# Week details
declare -A weeks
weeks[1]="Foundations & Data Models"
weeks[2]="Storage Layer"
weeks[3]="Embeddings & ML"
weeks[4]="Feature Engineering"
weeks[5]="Monitoring & Observability"
weeks[6]="Production Deployment"

total_completed=0
total_weeks=6

# Check each week
for week in {1..6}; do
    status=$(check_week_tests "$week-basics" 2>/dev/null || check_week_tests "$week" 2>/dev/null || echo "NOT_STARTED")
    exercises=$(count_completed_exercises "$week")

    case $status in
        COMPLETED)
            icon=$COMPLETED
            status_text="Completed"
            ((total_completed++))
            ;;
        IN_PROGRESS)
            icon=$IN_PROGRESS
            status_text="In Progress"
            ;;
        *)
            icon=$NOT_STARTED
            status_text="Not Started"
            ;;
    esac

    echo -e "Week $week: ${icon} ${status_text} - ${weeks[$week]}"
    if [ "$exercises" != "0/0" ]; then
        echo -e "        Exercises: ${exercises}"
    fi
done

echo ""
print_header "Overall Progress"

# Calculate percentage
percentage=$((total_completed * 100 / total_weeks))

echo -e "Completed Weeks: ${total_completed}/${total_weeks}"
echo -e "Progress: ${percentage}%"

# Progress bar
bar_length=50
filled=$((percentage * bar_length / 100))
empty=$((bar_length - filled))

printf "["
printf "${GREEN}%${filled}s${NC}" | tr ' ' '='
printf "%${empty}s" | tr ' ' '-'
printf "]\n"

echo ""

# Recommendations
if [ $total_completed -eq 0 ]; then
    print_warning "🎯 Recommendation: Start with Week 1!"
    echo "   cd week-1-basics && cat README.md"
elif [ $total_completed -eq 6 ]; then
    print_success "🎉 Congratulations! You've completed the entire learning path!"
    echo "   Consider building your own project or contributing improvements."
else
    next_week=$((total_completed + 1))
    print_warning "🎯 Recommendation: Continue with Week ${next_week}"
    echo "   ${weeks[$next_week]}"
fi

echo ""
print_header "Quick Commands"
echo ""
echo "Run all tests:        pytest learning-path/ -v"
echo "Check Week 1:         pytest learning-path/week-1-basics/tests/ -v"
echo "Run benchmarks:       python benchmark_performance.py --quick"
echo "Local testing:        ./test_local.sh --quick"
echo ""
