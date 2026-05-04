Set-Location $PSScriptRoot
Write-Host '--- API Server ---' -ForegroundColor Cyan
Write-Host 'Waiting 5s for Thrall to boot...' -ForegroundColor DarkGray
Start-Sleep -Seconds 5
.\venv\Scripts\python.exe main.py
