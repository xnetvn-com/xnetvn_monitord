#!/bin/bash
# Copyright 2026 xNetVN Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

#
# Script to run comprehensive tests for xNetVN Monitor Daemon
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}xNetVN Monitor Daemon - Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_ROOT/pytest.ini" ]; then
    echo -e "${RED}Error: pytest.ini not found. Are you in the project root?${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Warning: No virtual environment found.${NC}"
    echo -e "${YELLOW}It's recommended to create one: python3 -m venv venv${NC}"
    echo ""
fi

# Install dependencies
echo -e "${BLUE}Installing test dependencies...${NC}"
pip install -q -r requirements-dev.txt

echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Run different test suites
run_tests() {
    local test_type=$1
    local marker=$2
    local description=$3

    echo -e "${BLUE}Running ${description}...${NC}"
    
    if pytest -m "$marker" -v --tb=short; then
        echo -e "${GREEN}✓ ${description} passed${NC}"
        return 0
    else
        echo -e "${RED}✗ ${description} failed${NC}"
        return 1
    fi
}

FAILED=0

# Unit Tests
run_tests "unit" "unit" "Unit Tests" || FAILED=1
echo ""

# Integration Tests
if [ "${SKIP_INTEGRATION:-0}" = "0" ]; then
    run_tests "integration" "integration" "Integration Tests" || FAILED=1
    echo ""
fi

# Security Tests
run_tests "security" "security" "Security Tests" || FAILED=1
echo ""

# Generate coverage report
echo -e "${BLUE}Generating coverage report...${NC}"
pytest --cov=xnetvn_monitord --cov-report=html --cov-report=term-missing -q

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo -e "Coverage report: ${GREEN}htmlcov/index.html${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
