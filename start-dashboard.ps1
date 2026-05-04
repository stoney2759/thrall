Set-Location (Join-Path $PSScriptRoot 'dashboard')
Write-Host '--- Dashboard ---' -ForegroundColor Green
Write-Host 'Waiting 9s for API...' -ForegroundColor DarkGray
Start-Sleep -Seconds 9
npm run dev

