from __future__ import annotations

# Log files — one rotating file per running process. Windows cannot rename a file another
# process holds open, so two running Thrall processes never share one. thrall.py names the
# file by launch mode (constants/launcher.py LAUNCH_LOG_NAMES).
LOG_FILE_MAIN = "thrall.log"             # thrall.py "Webapp + Telegram" (the usual mode)
LOG_FILE_WEB = "thrall-web.log"          # thrall.py "Webapp only"
LOG_FILE_TELEGRAM = "thrall-telegram.log"  # thrall.py "Telegram only"
LOG_FILE_OTHER = "thrall-{process}"      # any other entry script, e.g. pytest / ad-hoc runs
LOG_FILE_ERRORS = "thrall_err.log"       # ERROR+ from all processes; low volume, not rotated
LOG_MAX_BYTES = 20 * 1024 * 1024         # rotate at 20 MB
LOG_BACKUP_COUNT = 5                     # keep .1 … .5 (~120 MB max per process)
LOG_DEFAULT_LEVEL = "INFO"               # release default; set [logging] level = "DEBUG" in config.toml for development
LOG_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}  # same numbers as Python's logging levels

# Third-party loggers that flood DEBUG (HTTP internals, Telegram long-polling) — WARNING+ only
QUIET_LOGGERS = ("httpcore", "httpx", "hpack", "telegram.ext", "telegram._bot", "urllib3", "asyncio")
