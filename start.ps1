#Requires -Version 5.1
# start.ps1 — Thrall full-stack launcher
# Opens all three services as tabs in a single Windows Terminal window.
# Launch order is enforced via Start-Sleep inside each tab's command.

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

# ── Step 2: Open Windows Terminal with 3 tabs ─────────────────────────────────
# Tabs open together. API waits 5s, Dashboard waits 10s — so Thrall is up first.

Section "Launching Windows Terminal"

Log "Opening 3 tabs: Telegram | API | Dashboard..." Cyan

# Wrap file paths in quotes to survive spaces in the project path.
$fTelegram  = "`"$Root\start-telegram.ps1`""
$fApi       = "`"$Root\start-api.ps1`""
$fDashboard = "`"$Root\start-dashboard.ps1`""

Start-Process wt -ArgumentList @(
    "new-tab", "--title", "Telegram",
    "powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $fTelegram,
    ";",
    "new-tab", "--title", "API",
    "powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $fApi,
    ";",
    "new-tab", "--title", "Dashboard",
    "powershell", "-NoExit", "-ExecutionPolicy", "Bypass", "-File", $fDashboard
)

Log "Windows Terminal opened." Green

# ── Done ──────────────────────────────────────────────────────────────────────

Section "All systems go"
Log "Telegram server  →  running (Telegram tab)" Green
Log "API server       →  http://localhost:8000   (API tab)" Green
Log "Dashboard        →  http://localhost:5173   (Dashboard tab)" Green
Write-Host ""
Log "CPU affinity (optional — run after services are up):" DarkGray
Log '  Get-Process python | ForEach-Object { $_.ProcessorAffinity = 15 }' DarkGray
Write-Host ""
