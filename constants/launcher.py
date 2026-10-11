from __future__ import annotations

# thrall.py — the single launcher
MODE_ALL = "all"            # webapp + Telegram in ONE process (shared memory)
MODE_WEB = "web"
MODE_TELEGRAM = "telegram"
MODE_CLI = "cli"
LAUNCH_MODES = (MODE_ALL, MODE_WEB, MODE_TELEGRAM, MODE_CLI)

# (menu key, mode, label) — order shown in the menu
LAUNCH_MENU = (
    ("1", MODE_ALL, "Webapp + Telegram   (recommended — one process, shared memory)"),
    ("2", MODE_WEB, "Webapp only"),
    ("3", MODE_TELEGRAM, "Telegram only"),
    ("4", MODE_CLI, "Terminal chat"),
)
LAUNCH_DEFAULT_KEY = "1"

# Log file per mode (logs/<name>.log) — a mode never shares a file with another running mode
LAUNCH_LOG_NAMES = {MODE_ALL: "thrall", MODE_WEB: "thrall-web", MODE_TELEGRAM: "thrall-telegram", MODE_CLI: "thrall-cli"}

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DASHBOARD_DIR = "dashboard"
DASHBOARD_BUILT_FILE = "dashboard/dist/index.html"
DASHBOARD_DEPS_DIR = "dashboard/node_modules"   # missing on a fresh clone → npm install first
DASHBOARD_SOURCE_DIRS = ("dashboard/src",)
DASHBOARD_SOURCE_FILES = ("dashboard/index.html", "dashboard/package.json", "dashboard/vite.config.ts",
                          "dashboard/tailwind.config.js")

BANNER = (
    ("  ████████╗██╗  ██╗██████╗  █████╗ ██╗     ██╗", "dark_magenta"),
    ("     ██╔══╝██║  ██║██╔══██╗██╔══██╗██║     ██║", "magenta"),
    ("     ██║   ███████║██████╔╝███████║██║     ██║", "magenta"),
    ("     ██║   ██╔══██║██╔══██╗██╔══██║██║     ██║", "dark_magenta"),
    ("     ██║   ██║  ██║██║  ██║██║  ██║███████╗███████╗", "dark_magenta"),
    ("     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝", "dark_gray"),
)
TAGLINE = "  Thrall 2.0"

# Setup messages — shown instead of a crash when config needs the user's attention
CONFIG_PATH = "config/config.toml"
CONFIG_MISSING_MSG = "config/config.toml not found — copy config/config.example.toml to config/config.toml first."
CONFIG_INVALID_MSG = "config/config.toml has a mistake Thrall can't read: {error}"
CONFIG_INVALID_HINT = "Fix that line (text values need quotes, lists look like [123, 456]) and start again."
TELEGRAM_NO_USERS_MSG = ("Telegram has no allowed users yet — add your Telegram user id to allowed_user_ids "
                         "under [transports.telegram] in config/config.toml (message @userinfobot to get it).")

# ANSI colours (same palette as the old start.ps1)
COLOURS = {
    "dark_magenta": "\033[35m", "magenta": "\033[95m", "dark_gray": "\033[90m", "white": "\033[97m",
    "cyan": "\033[96m", "green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "reset": "\033[0m",
}
