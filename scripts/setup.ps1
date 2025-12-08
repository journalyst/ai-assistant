# PowerShell setup script for Journalyst AI Assistant
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

Write-Host "[Setup] Creating virtual environment .venv" -ForegroundColor Cyan
python -m venv .venv

Write-Host "[Setup] Activating virtual environment" -ForegroundColor Cyan
.\.venv\Scripts\activate.ps1

Write-Host "[Setup] Installing UV package manager" -ForegroundColor Cyan
python -m pip install --upgrade pip uv

Write-Host "[Setup] Installing requirements with UV" -ForegroundColor Cyan
uv pip install -r requirements.txt

Write-Host "[Setup] Completed." -ForegroundColor Green
Write-Host "[Info] To activate: .venv\Scripts\activate.ps1" -ForegroundColor Yellow
