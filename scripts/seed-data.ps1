# Journalyst AI Assistant - Data Seeding Script
# Seeds both PostgreSQL database and Qdrant vector database

param(
    [switch]$PostgresOnly,
    [switch]$QdrantOnly,
    [switch]$IncludeLegacyData,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { param($msg) Write-Host $msg -ForegroundColor Green }
function Write-Info { param($msg) Write-Host $msg -ForegroundColor Cyan }
function Write-Warn { param($msg) Write-Host $msg -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host $msg -ForegroundColor Red }

# Help message
if ($Help) {
    Write-Host @"
Journalyst AI Assistant - Data Seeding Script

Usage: .\scripts\seed-data.ps1 [options]

Options:
    -PostgresOnly    Seed only PostgreSQL database
    -QdrantOnly      Seed only Qdrant vector database (journals)
    -IncludeLegacyData  Also seed legacy INSERT rows from sample_data/seed_data.sql
    -Help            Show this help message

Examples:
    .\scripts\seed-data.ps1                 # Seed schema + normalized JSON + journals
    .\scripts\seed-data.ps1 -PostgresOnly   # Seed only PostgreSQL
    .\scripts\seed-data.ps1 -QdrantOnly     # Seed only Qdrant
    .\scripts\seed-data.ps1 -IncludeLegacyData # Also load old sample rows

Requirements:
    - Python virtual environment at .venv/
    - PostgreSQL running and accessible
    - Qdrant running at localhost:6333
    - Redis running at localhost:6379 (for embedding cache)
"@
    exit 0
}

# Get script directory and project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Change to project root
Push-Location $ProjectRoot

try {
    Write-Host ""
    Write-Host "========================================"
    Write-Info "   Journalyst Data Seeding Script"
    Write-Host "========================================"
    Write-Host ""

    # Check virtual environment
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Err "Virtual environment not found at .venv/"
        Write-Err "Run: python -m venv .venv && .\.venv\Scripts\Activate.ps1 && pip install -r requirements.txt"
        exit 1
    }

    # Seed PostgreSQL
    if (-not $QdrantOnly) {
        Write-Host ""
        Write-Info ">>> Seeding PostgreSQL Database..."
        Write-Host "----------------------------------------"
        
        if ($IncludeLegacyData) {
            $env:SEED_INCLUDE_LEGACY_DATA = "true"
            Write-Warn "Legacy SQL INSERT seed is ENABLED"
        } else {
            $env:SEED_INCLUDE_LEGACY_DATA = "false"
            Write-Info "Legacy SQL INSERT seed is disabled (schema-only baseline)"
        }

        & $VenvPython -m src.data_seeding.seed_postgres
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "PostgreSQL seeding completed!"
        } else {
            Write-Err "PostgreSQL seeding failed!"
            exit 1
        }

        if (Test-Path "sample_data/sample_options_trades_jan_feb_2026.json") {
            Write-Host ""
            Write-Info ">>> Seeding Normalized Trades JSON..."
            Write-Host "----------------------------------------"

            & $VenvPython -m src.data_seeding.seed_trades_normalized

            if ($LASTEXITCODE -eq 0) {
                Write-Success "Normalized trades seeding completed!"
            } else {
                Write-Err "Normalized trades seeding failed!"
                exit 1
            }
        } else {
            Write-Warn "sample_data/sample_options_trades_jan_feb_2026.json not found - skipping normalized trades seeding"
        }
    }

    # Seed Qdrant (journals)
    if (-not $PostgresOnly) {
        Write-Host ""
        Write-Info ">>> Seeding Qdrant Vector Database (Journals)..."
        Write-Host "----------------------------------------"
        
        & $VenvPython -m src.data_seeding.seed_journals
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Qdrant seeding completed!"
        } else {
            Write-Err "Qdrant seeding failed!"
            exit 1
        }
    }

    # Summary
    Write-Host ""
    Write-Host "========================================"
    Write-Success "   All Seeding Complete!"
    Write-Host "========================================"
    Write-Host ""
    
    if (-not $QdrantOnly) {
        Write-Host "PostgreSQL Objects:"
        Write-Host "  - final schema from sample_data/seed_data.sql (DDL)"
        Write-Host "  - normalized trades from sample_options_trades_jan_feb_2026.json"
        if ($IncludeLegacyData) {
            Write-Host "  - legacy SQL INSERT sample rows (enabled)"
        }
        Write-Host ""
    }
    
    if (-not $PostgresOnly) {
        Write-Host "Qdrant Collection:"
        Write-Host "  - journal_entries (90 journal entries)"
        Write-Host ""
    }

} catch {
    Write-Err "An error occurred: $_"
    exit 1
} finally {
    Pop-Location
}
