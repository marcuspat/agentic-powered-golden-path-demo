#!/bin/bash

# Phase 1: Prerequisites Verification Tests
# Tests for Docker, kubectl, git, GitHub token, OpenAI API key, and Python

set -e  # Exit on any failure
set -u  # Treat unset variables as errors

# Test colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
PASSED=0
FAILED=0
TOTAL_TESTS=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "Testing $test_name... "

    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        FAILED=$((FAILED + 1))
        echo "  Command: $test_command"
        echo "  Error: $(eval "$test_command" 2>&1 | head -n 1)"
        return 1
    fi
}

# Test with description
run_test_with_desc() {
    local test_name="$1"
    local description="$2"
    local test_command="$3"

    echo ""
    echo "=== $test_name ==="
    echo "Description: $description"
    run_test "$test_name" "$test_command"
}

# Main test suite
echo "========================================"
echo "Phase 1: Prerequisites Verification Tests"
echo "========================================"

# Docker Tests
run_test_with_desc "Docker Installation" \
    "Verify Docker is installed and running" \
    "docker --version && docker info"

run_test_with_desc "Docker Daemon" \
    "Verify Docker daemon is accessible" \
    "docker ps"

# kubectl Tests
run_test_with_desc "kubectl Installation" \
    "Verify kubectl is installed" \
    "kubectl version --client"

run_test_with_desc "kubectl Cluster Access" \
    "Verify kubectl can access cluster" \
    "kubectl cluster-info"

run_test_with_desc "kubectl Node Access" \
    "Verify kubectl can list nodes" \
    "kubectl get nodes"

# Git Tests
run_test_with_desc "Git Installation" \
    "Verify git is installed" \
    "git --version"

run_test_with_desc "Git Configuration" \
    "Verify git is configured with user info" \
    "git config --global user.name && git config --global user.email"

# GitHub Tests
run_test_with_desc "GitHub Token" \
    "Verify GitHub token is available" \
    "test -n \"\${GITHUB_TOKEN:-}\""

run_test_with_desc "GitHub Authentication" \
    "Verify GitHub token is valid" \
    "curl -s -H \"Authorization: token \$GITHUB_TOKEN\" https://api.github.com/user | grep -q \"login\""

run_test_with_desc "GitHub Username" \
    "Verify GitHub username is configured" \
    "test -n \"\${GITHUB_USERNAME:-}\""

# OpenAI API Tests
run_test_with_desc "OpenAI API Key" \
    "Verify OpenAI API key is available" \
    "test -n \"\${OPENAI_API_KEY:-}\""

run_test_with_desc "OpenAI API Access" \
    "Verify OpenAI API key is valid" \
    "curl -s -H \"Authorization: Bearer \$OPENAI_API_KEY\" https://api.openai.com/v1/models | grep -q \"object\""

# Python Tests
run_test_with_desc "Python Installation" \
    "Verify Python 3.9+ is installed" \
    "python3 --version | grep -E 'Python 3\.[9-9]|[1-9][0-9]'"

run_test_with_desc "pip Installation" \
    "Verify pip is installed" \
    "pip3 --version"

run_test_with_desc "Python Virtual Environment" \
    "Verify Python venv module is available" \
    "python3 -m venv --help"

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All prerequisite tests passed!${NC}"
    SUCCESS_RATE=100
else
    SUCCESS_RATE=$(( (PASSED * 100) / TOTAL_TESTS ))
    echo -e "${YELLOW}Success Rate: $SUCCESS_RATE%${NC}"
    if [ $SUCCESS_RATE -lt 95 ]; then
        echo -e "${RED}Warning: Success rate below 95% threshold${NC}"
    fi
fi

# Generate JSON report
cat > /tmp/prerequisites-test-report.json << EOF
{
  "test_phase": "Phase 1: Prerequisites",
  "timestamp": "$(date -Iseconds)",
  "total_tests": $TOTAL_TESTS,
  "passed_tests": $PASSED,
  "failed_tests": $FAILED,
  "success_rate": $SUCCESS_RATE,
  "recommendations": [
$(if [ $FAILED -gt 0 ]; then
    echo "    \"Fix failed prerequisite tests before proceeding\""
else
    echo "    \"All prerequisites validated successfully\""
fi)
  ]
}
EOF

echo "Test report saved to: /tmp/prerequisites-test-report.json"

# Exit with error if any tests failed
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Error: $FAILED prerequisite test(s) failed${NC}"
    exit 1
else
    echo -e "${GREEN}Success: All prerequisite tests passed${NC}"
    exit 0
fi