#!/bin/bash
# Run the FastAPI server
# Usage: ./docker_scripts/run-api.sh

set -e

echo -e "\033[0;36m[Run] Starting uvicorn server\033[0m"

export PYTHONUNBUFFERED=1

python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 "$@"
