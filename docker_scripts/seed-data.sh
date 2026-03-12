#!/bin/bash
# Journalyst AI Assistant - Data Seeding Script (Docker/Linux)
# Seeds both PostgreSQL database and Qdrant vector database

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_success() { echo -e "${GREEN}$1${NC}"; }
print_info() { echo -e "${CYAN}$1${NC}"; }
print_warn() { echo -e "${YELLOW}$1${NC}"; }
print_err() { echo -e "${RED}$1${NC}"; }

# Parse arguments
POSTGRES_ONLY=false
QDRANT_ONLY=false
INCLUDE_LEGACY_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --postgres-only)
            POSTGRES_ONLY=true
            shift
            ;;
        --qdrant-only)
            QDRANT_ONLY=true
            shift
            ;;
        --help|-h)
            cat << EOF
Journalyst AI Assistant - Data Seeding Script (Docker)

Usage: ./docker_scripts/seed-data.sh [options]

Options:
    --postgres-only    Seed only PostgreSQL database
    --qdrant-only      Seed only Qdrant vector database (journals)
    --include-legacy-data  Also seed legacy INSERT rows from sample_data/seed_data.sql
    --help, -h         Show this help message

Examples:
    ./docker_scripts/seed-data.sh                 # Seed schema + normalized JSON + journals
    ./docker_scripts/seed-data.sh --postgres-only # Seed only PostgreSQL
    ./docker_scripts/seed-data.sh --qdrant-only   # Seed only Qdrant
    ./docker_scripts/seed-data.sh --include-legacy-data  # Also load old sample rows

EOF
            exit 0
            ;;
        --include-legacy-data)
            INCLUDE_LEGACY_DATA=true
            shift
            ;;
        *)
            print_err "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "========================================"
print_info "   Journalyst Data Seeding Script"
echo "========================================"
echo ""

# Seed PostgreSQL
if [ "$QDRANT_ONLY" = false ]; then
    echo ""
    print_info ">>> Seeding PostgreSQL Database..."
    echo "----------------------------------------"
    
    if [ "$INCLUDE_LEGACY_DATA" = true ]; then
        export SEED_INCLUDE_LEGACY_DATA=true
        print_warn "Legacy SQL INSERT seed is ENABLED"
    else
        export SEED_INCLUDE_LEGACY_DATA=false
        print_info "Legacy SQL INSERT seed is disabled (schema-only baseline)"
    fi

    python -m src.data_seeding.seed_postgres
    
    if [ $? -eq 0 ]; then
        print_success "PostgreSQL seeding completed!"
    else
        print_err "PostgreSQL seeding failed!"
        exit 1
    fi

    if [ -f "sample_data/sample_options_trades_jan_feb_2026.json" ]; then
        echo ""
        print_info ">>> Seeding Normalized Trades JSON..."
        echo "----------------------------------------"

        python -m src.data_seeding.seed_trades_normalized

        if [ $? -eq 0 ]; then
            print_success "Normalized trades seeding completed!"
        else
            print_err "Normalized trades seeding failed!"
            exit 1
        fi
    else
        print_warn "sample_data/sample_options_trades_jan_feb_2026.json not found - skipping normalized trades seeding"
    fi
fi

# Seed Qdrant (journals)
if [ "$POSTGRES_ONLY" = false ]; then
    echo ""
    print_info ">>> Seeding Qdrant Vector Database (Journals)..."
    echo "----------------------------------------"
    
    python -m src.data_seeding.seed_journals
    
    if [ $? -eq 0 ]; then
        print_success "Qdrant seeding completed!"
    else
        print_err "Qdrant seeding failed!"
        exit 1
    fi
fi

# Summary
echo ""
echo "========================================"
print_success "   All Seeding Complete!"
echo "========================================"
echo ""

if [ "$QDRANT_ONLY" = false ]; then
    echo "PostgreSQL Objects:"
    echo "  - final schema from sample_data/seed_data.sql (DDL)"
    echo "  - normalized trades from sample_options_trades_jan_feb_2026.json"
    if [ "$INCLUDE_LEGACY_DATA" = true ]; then
        echo "  - legacy SQL INSERT sample rows (enabled)"
    fi
    echo ""
fi

if [ "$POSTGRES_ONLY" = false ]; then
    echo "Qdrant Collection:"
    echo "  - journal_entries (90 journal entries)"
    echo ""
fi
