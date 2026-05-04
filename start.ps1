#Requires -Version 5.1
# start.ps1 — Thrall full-stack launcher
# Builds the dashboard, then opens Telegram + API as tabs in Windows Terminal.
# Dashboard is served statically by the API at http://localhost:8000

$Root      = $PSScriptRoot
$Dashboard = Join-Path $Root "dashboard"

# ── Helpers ───────────────────────────────────────────────────────────────────

function Log {
    param([string]$Msg, [string]$Color = "Cyan")
    Write-Host "  $(Get-Date -Format 'HH:mm:ss')  $Msg" -ForegroundColor $Color
}

function Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "  $Title" -ForegroundColor White
    Write-Host ("  " + ("─" * 50)) -ForegroundColor DarkGray
}

# ── Banner ────────────────────────────────────────────────────────────────────

Clear-Host
Write-Host ""
Write-Host "  ████████╗██╗  ██╗██████╗  █████╗ ██╗     ██╗" -ForegroundColor DarkMagenta
Write-Host "     ██╔══╝██║  ██║██╔══██╗██╔══██╗██║     ██║" -ForegroundColor Magenta
Write-Host "     ██║   ███████║██████╔╝███████║██║     ██║" -ForegroundColor Magenta
Write-Host "     ██║   ██╔══██║██╔══██╗██╔══██║██║     ██║" -ForegroundColor DarkMagenta
Write-Host "     ██║   ██║  ██║██║  ██║██║  ██║███████╗███████╗" -ForegroundColor DarkMagenta
Write-Host "     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝" -ForegroundColor DarkGray
Write-Host "  Thrall 2.0 — Full Stack Launcher" -ForegroundColor DarkGray
Write-Host ""

# ── Check for Windows Terminal ────────────────────────────────────────────────

if (-not (Get-Command wt -ErrorAction SilentlyContinue)) {
    Write-Host "  Windows Terminal (wt) not found." -ForegroundColor Red
    Write-Host "  Install it from the Microsoft Store, or run each service manually." -ForegroundColor DarkGray
    exit 1
}

# ── Step 1: Kill existing processes ──────────────────────────────────────────

Section "Stopping existing processes"

$pyProcs = Get-Process -Name python -ErrorAction SilentlyContinue
if ($pyProcs) {
    Log "Found $($pyProcs.Count) Python process(es) — stopping..." Yellow
    $pyProcs | Stop-Process -Force -Confirm:$false
    Log "Python processes stopped." Green
} else {
    Log "No Python processes running." DarkGray
}

$ndProcs = Get-Process -Name node -ErrorAction SilentlyContinue
if ($ndProcs) {
    Log "Found $($ndProcs.Count) Node process(es) — stopping..." Yellow
    $ndProcs | Stop-Process -Force -Confirm:$false
    Log "Node processes stopped." Green
} else {
    Log "No Node processes running." DarkGray
}

Log "Waiting 2s for ports to clear..." DarkGray
Start-Sleep -Seconds 2

# ── Step 2: Build dashboard ───────────────────────────────────────────────────

Section "Building dashboard"

Log "Running npm run build..." Cyan
Push-Location $Dashboard
npm run build 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
$buildExit = $LASTEXITCODE
Pop-Location

if ($buildExit -ne 0) {
    Log "Dashboard build failed (exit $buildExit). Aborting." Red
    exit 1
}
Log "Dashboard built — will be served at http://localhost:8000" Green

# ── Step 3: Open Windows Terminal with 2 tabs ─────────────────────────────────

Section "Launching Windows Terminal"

Log "Opening 2 tabs: Telegram | API..." Cyan

$fTelegram = "`"$Root\start-telegram.ps1`""
$fApi      = "`"$Root\start-api.ps1`""

Start-Process wt -ArgumentList @(
    "new-tab", "--title", "Telegram",
    "powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $fTelegram,
    ";",
    "new-tab", "--title", "API",
    "powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $fApi
)

Log "Windows Terminal opened." Green

# ── Done ──────────────────────────────────────────────────────────────────────

Section "All systems go"
Log "Telegram server  →  running (Telegram tab)" Green
Log "API + Dashboard  →  http://localhost:8000   (API tab)" Green
Write-Host ""
Log "CPU affinity (optional — run after services are up):" DarkGray
Log '  Get-Process python | ForEach-Object { $_.ProcessorAffinity = 15 }' DarkGray
Write-Host ""
