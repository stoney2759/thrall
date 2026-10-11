"""Thrall — the one launcher.

    python thrall.py                 asks what to start
    python thrall.py --all           webapp + Telegram in one process (shared memory)
    python thrall.py --web           webapp only
    python thrall.py --telegram      Telegram only
    python thrall.py --cli           terminal chat
    add --no-build to skip rebuilding the webapp

Runs itself with the project's venv Python if one exists, builds the webapp when it is
missing or out of date, and never stops other programs — a busy port is reported instead.
"""
from __future__ import annotations
import argparse
import asyncio
import os
import socket
import subprocess
import sys
import tomllib
import warnings
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from constants.launcher import (  # noqa: E402 — needs ROOT on sys.path
    MODE_ALL, MODE_WEB, MODE_TELEGRAM, MODE_CLI, LAUNCH_MENU, LAUNCH_DEFAULT_KEY, LAUNCH_LOG_NAMES,
    DEFAULT_HOST, DEFAULT_PORT, DASHBOARD_DIR, DASHBOARD_BUILT_FILE, DASHBOARD_SOURCE_DIRS,
    DASHBOARD_SOURCE_FILES, BANNER, TAGLINE, COLOURS,
)


# ── Console output (same look as the old start.ps1) ──────────────────────────

def _enable_ansi() -> None:
    """Windows consoles need virtual-terminal processing switched on for colours."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def colour(text: str, name: str) -> str:
    return f"{COLOURS[name]}{text}{COLOURS['reset']}"


def log(message: str, name: str = "cyan") -> None:
    print(f"  {datetime.now():%H:%M:%S}  {colour(message, name)}")


def section(title: str) -> None:
    print()
    print(f"  {colour(title, 'white')}")
    print(f"  {colour('─' * 50, 'dark_gray')}")


def banner() -> None:
    print()
    for line, shade in BANNER:
        print(colour(line, shade))
    print(colour(TAGLINE, "dark_gray"))
    print()


# ── Checks ───────────────────────────────────────────────────────────────────

def venv_python() -> Path | None:
    for candidate in (ROOT / "venv" / "Scripts" / "python.exe", ROOT / "venv" / "bin" / "python",
                      ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if candidate.exists():
            return candidate
    return None


def ensure_venv() -> None:
    """Re-run this script with the project's venv Python when started with another one."""
    venv = venv_python()
    if venv is None or Path(sys.prefix).resolve() == venv.parent.parent.resolve():
        return
    result = subprocess.run([str(venv), str(Path(__file__).resolve()), *sys.argv[1:]])
    sys.exit(result.returncode)


def load_config() -> dict:
    path = ROOT / "config" / "config.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def server_address(config: dict) -> tuple[str, int]:
    server = config.get("server", {})
    return str(server.get("host", DEFAULT_HOST)), int(server.get("port", DEFAULT_PORT))


def port_in_use(host: str, port: int) -> bool:
    probe = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((probe, port)) == 0


def dashboard_needs_build() -> bool:
    built = ROOT / DASHBOARD_BUILT_FILE
    if not built.exists():
        return True
    built_at = built.stat().st_mtime
    sources = [ROOT / f for f in DASHBOARD_SOURCE_FILES]
    for folder in DASHBOARD_SOURCE_DIRS:
        sources += [p for p in (ROOT / folder).rglob("*") if p.is_file()]
    return any(p.exists() and p.stat().st_mtime > built_at for p in sources)


def build_dashboard() -> bool:
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    log("Building the webapp (npm run build)…")
    try:
        result = subprocess.run([npm, "run", "build"], cwd=ROOT / DASHBOARD_DIR, capture_output=True, text=True)
    except FileNotFoundError:
        log("npm not found — install Node.js to build the webapp.", "red")
        return False
    if result.returncode != 0:
        log("Webapp build failed:", "red")
        print(result.stdout[-2000:] + result.stderr[-2000:])
        return False
    log("Webapp built.", "green")
    return True


def telegram_ready(config: dict) -> tuple[bool, str]:
    if not config.get("transports", {}).get("telegram", {}).get("enabled", False):
        return False, "Telegram is disabled in config ([transports.telegram] enabled = false)."
    if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() and "TELEGRAM_BOT_TOKEN" not in _env_file_keys():
        return False, "TELEGRAM_BOT_TOKEN is not set (add it to .env)."
    return True, ""


def _env_file_keys() -> set[str]:
    path = ROOT / ".env"
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line and line.split("=", 1)[1].strip():
            keys.add(line.split("=", 1)[0].strip())
    return keys


# ── Choosing what to start ───────────────────────────────────────────────────

def choose_mode() -> str:
    section("What do you want to start?")
    for key, _mode, label in LAUNCH_MENU:
        print(f"   {colour(key + ')', 'magenta')} {label}")
    print()
    while True:
        try:
            answer = input(f"  > [{LAUNCH_DEFAULT_KEY}] ").strip() or LAUNCH_DEFAULT_KEY
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        for key, mode, _label in LAUNCH_MENU:
            if answer == key:
                return mode
        print(colour(f"  Pick {', '.join(k for k, _, _ in LAUNCH_MENU)}.", "yellow"))


# ── Running ──────────────────────────────────────────────────────────────────

async def run_services(web: bool, telegram: bool, host: str, port: int) -> None:
    tasks = []
    server = None
    if web:
        import uvicorn
        server = uvicorn.Server(uvicorn.Config("server.app:app", host=host, port=port, loop="none",
                                               log_level="warning"))
        tasks.append(asyncio.create_task(server.serve(), name="webapp"))
    if telegram:
        from transports.telegram.bot import run as run_telegram
        tasks.append(asyncio.create_task(run_telegram(), name="telegram"))
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task.exception():
                log(f"{task.get_name()} stopped: {type(task.exception()).__name__}: {task.exception()}", "red")
    finally:
        if server is not None:
            server.should_exit = True
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        from services.mcp import lifecycle as mcp_lifecycle
        await mcp_lifecycle.stop()


def main() -> None:
    ensure_venv()
    _enable_ansi()
    if sys.platform == "win32":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    parser = argparse.ArgumentParser(description="Start Thrall.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="webapp + Telegram in one process")
    group.add_argument("--web", action="store_true", help="webapp only")
    group.add_argument("--telegram", action="store_true", help="Telegram only")
    group.add_argument("--cli", action="store_true", help="terminal chat")
    parser.add_argument("--no-build", action="store_true", help="don't rebuild the webapp")
    args = parser.parse_args()

    os.chdir(ROOT)
    banner()
    if args.all:
        mode = MODE_ALL
    elif args.web:
        mode = MODE_WEB
    elif args.telegram:
        mode = MODE_TELEGRAM
    elif args.cli:
        mode = MODE_CLI
    else:
        mode = choose_mode()

    config = load_config()
    if not config:
        log("config/config.toml not found — copy config/config.example.toml to config/config.toml first.", "red")
        sys.exit(1)

    web = mode in (MODE_ALL, MODE_WEB)
    telegram = mode in (MODE_ALL, MODE_TELEGRAM)
    host, port = server_address(config)

    section("Checking")
    if telegram:
        ok, reason = telegram_ready(config)
        if not ok:
            log(reason, "yellow" if web else "red")
            if not web:
                sys.exit(1)
            log("Starting the webapp without Telegram.", "yellow")
            telegram = False
        else:
            log("Telegram ready.", "green")
    if web:
        if port_in_use(host, port):
            log(f"Port {port} is already in use — is Thrall already running? Nothing was stopped.", "red")
            sys.exit(1)
        if args.no_build:
            log("Skipping webapp build (--no-build).", "dark_gray")
        elif dashboard_needs_build():
            if not build_dashboard():
                log("Continuing with the existing webapp build (if any).", "yellow")
        else:
            log("Webapp is up to date.", "green")

    from bootstrap.startup import start
    start(log_name=LAUNCH_LOG_NAMES[mode])

    if mode == MODE_CLI:
        section("Terminal chat")
        from transports.cli.interface import run as run_cli
        run_cli()
        return

    section("All systems go")
    if web:
        log(f"Webapp     →  http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}", "green")
    if telegram:
        log("Telegram   →  running", "green")
    log(f"Logs       →  logs/{LAUNCH_LOG_NAMES[mode]}.log", "dark_gray")
    log("Press Ctrl+C to stop.", "dark_gray")
    print()
    try:
        asyncio.run(run_services(web, telegram, host, port))
    except KeyboardInterrupt:
        pass
    print()
    log("Thrall stopped.", "dark_gray")


if __name__ == "__main__":
    main()
