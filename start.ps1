# Thrall 2.0 — Boot Script
# Kills any running Python processes, then starts the Telegram server.

Write-Host "Stopping existing Python processes..."
Get-Process -Name "python" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Activating venv..."
& "$PSScriptRoot\venv\Scripts\Activate.ps1"

Write-Host "Starting Thrall..."
Set-Location $PSScriptRoot
python telegram_server.py
