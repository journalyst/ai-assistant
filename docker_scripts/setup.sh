#!/bin/bash
# Setup script for Journalyst AI Assistant (Docker/Linux)
# This script is typically not needed in Docker as dependencies are installed during build
# Usage: ./docker_scripts/setup.sh

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}[Setup] Creating virtual environment .venv${NC}"
python -m venv .venv

echo -e "${CYAN}[Setup] Activating virtual environment${NC}"
source .venv/bin/activate

echo -e "${CYAN}[Setup] Installing UV package manager${NC}"
python -m pip install --upgrade pip uv

echo -e "${CYAN}[Setup] Installing requirements with UV${NC}"
uv pip install -r requirements.txt

echo -e "${GREEN}[Setup] Completed.${NC}"
echo -e "${YELLOW}[Info] To activate: source .venv/bin/activate${NC}"
