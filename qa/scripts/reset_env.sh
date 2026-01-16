#!/usr/bin/env bash
# =============================================================================
# TokenMetric Test Environment Reset Script
# =============================================================================
#
# This script resets the test environment to a clean state.
# It resets the database, blockchain state, and cleans temporary files.
#
# Usage: ./qa/scripts/reset_env.sh [--hard]
#   --hard: Also clears Docker containers and volumes
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${GREEN}=== TokenMetric Test Environment Reset ===${NC}"
echo ""

# Parse arguments
HARD_RESET=false
if [[ "$1" == "--hard" ]]; then
    HARD_RESET=true
    echo -e "${YELLOW}Performing HARD reset (includes Docker)${NC}"
    echo ""
fi

# =============================================================================
# 1. Reset Database
# =============================================================================
echo -e "${GREEN}[1/5] Resetting database...${NC}"

# Stop any running postgres containers
if command -v docker >/dev/null 2>&1; then
    docker ps | grep -q "tokenmetric-postgres" && docker stop tokenmetric-postgres 2>/dev/null || true
fi

# Remove test database files
rm -f "$PROJECT_ROOT/backend/test.db"
rm -f "$PROJECT_ROOT/backend/*.db"
rm -f "$PROJECT_ROOT/backend/*.db-shm"
rm -f "$PROJECT_ROOT/backend/*.db-wal"

echo "  ✓ Database files removed"

# =============================================================================
# 2. Reset Blockchain State
# =============================================================================
echo -e "${GREEN}[2/5] Resetting blockchain state...${NC}"

# Clean Foundry artifacts
cd "$PROJECT_ROOT/contracts"
forge clean 2>/dev/null || true

echo "  ✓ Foundry cache cleaned"

# =============================================================================
# 3. Clean Test Artifacts
# =============================================================================
echo -e "${GREEN}[3/5] Cleaning test artifacts...${NC}"

# Remove coverage reports
rm -f "$PROJECT_ROOT/contracts/lcov.info"
rm -f "$PROJECT_ROOT/contracts/coverage.txt"
rm -rf "$PROJECT_ROOT/contracts/artifacts"

# Remove gas snapshots
rm -f "$PROJECT_ROOT/contracts/.gas-snapshot"

echo "  ✓ Test artifacts removed"

# =============================================================================
# 4. Clean Python Cache
# =============================================================================
echo -e "${GREEN}[4/5] Cleaning Python cache...${NC}"

cd "$PROJECT_ROOT/backend"

# Remove __pycache__ and .pytest_cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".coverage" -exec rm -rf {} + 2>/dev/null || true
rm -f .coverage
rm -f coverage.xml

echo "  ✓ Python cache cleaned"

# =============================================================================
# 5. Hard Reset (Optional)
# =============================================================================
if [ "$HARD_RESET" = true ]; then
    echo -e "${GREEN}[5/5] Performing hard reset...${NC}"

    # Remove all Docker containers and volumes
    cd "$PROJECT_ROOT"
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose down -v 2>/dev/null || true
    elif command -v docker >/dev/null 2>&1; then
        docker compose down -v 2>/dev/null || true
    fi

    # Prune Docker system
    docker system prune -f 2>/dev/null || true

    echo "  ✓ Docker containers and volumes removed"
else
    echo -e "${GREEN}[5/5] Skipping hard reset${NC}"
fi

# =============================================================================
# Reinitialize Environment
# =============================================================================
echo ""
echo -e "${GREEN}=== Reinitializing Test Environment ===${NC}"

# Start Docker services if needed
if [ "$HARD_RESET" = true ]; then
    echo "Starting Docker services..."
    cd "$PROJECT_ROOT"
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose up -d postgres
    elif command -v docker >/dev/null 2>&1; then
        docker compose up -d postgres
    fi
    sleep 5
fi

echo ""
echo -e "${GREEN}=== Test Environment Reset Complete ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Run smart contract tests: cd contracts && forge test"
echo "  2. Run backend tests: cd backend && pytest"
echo "  3. Run mobile tests: cd mobile && npm run test:all"
