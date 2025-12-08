# Run the FastAPI server with reload
# Usage: powershell -ExecutionPolicy Bypass -File scripts\run-api.ps1

Write-Host "[Run] Activating virtual environment" -ForegroundColor Cyan
.\.venv\Scripts\activate.ps1

$env:PYTHONUNBUFFERED="1"

Write-Host "[Run] Starting uvicorn server" -ForegroundColor Cyan
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
