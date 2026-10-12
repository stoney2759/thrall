"""Restart helper — runs as its own process so it outlives the Thrall process it restarts.

    python -m thrall.tools.system.restart_helper <root_pid> <port> <cwd> <command-json>

Waits, kills ONLY the Thrall process tree rooted at root_pid (never itself), waits for the
processes and the webapp port to be free, then relaunches Thrall with its original command.
Nothing else on the machine is touched.
"""
from __future__ import annotations
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from constants.restart import (  # noqa: E402 — needs ROOT on sys.path
    RESTART_DELAY_SECONDS, RESTART_KILL_WAIT_SECONDS, RESTART_PORT_WAIT_SECONDS, RESTART_LOG_FILE,
)


def _log(message: str) -> None:
    path = ROOT / RESTART_LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def _is_helper(proc) -> bool:
    """This helper and the venv launcher stub that started it (killing the stub would kill us too)."""
    try:
        return any("restart_helper" in part for part in proc.cmdline())
    except Exception:
        return False


def kill_tree(root_pid: int, keep_pid: int) -> int:
    """Kill root_pid and all its descendants except this helper. Returns how many were killed."""
    import psutil
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return 0
    procs = [p for p in root.children(recursive=True) if p.pid != keep_pid and not _is_helper(p)] + [root]
    for p in procs:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    psutil.wait_procs(procs, timeout=RESTART_KILL_WAIT_SECONDS)
    return len(procs)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def relaunch(command: list[str], cwd: str) -> int:
    if sys.platform == "win32":
        proc = subprocess.Popen(command, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        log = open(ROOT / RESTART_LOG_FILE, "a", encoding="utf-8")
        proc = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=log, start_new_session=True)
    return proc.pid


def main(argv: list[str]) -> int:
    root_pid, port, cwd, command = int(argv[0]), int(argv[1]), argv[2], json.loads(argv[3])
    _log(f"restart requested: root={root_pid} port={port} cmd={command}")
    time.sleep(RESTART_DELAY_SECONDS)
    killed = kill_tree(root_pid, keep_pid=os.getpid())
    _log(f"killed {killed} process(es)")
    deadline = time.monotonic() + RESTART_PORT_WAIT_SECONDS
    while not port_free(port) and time.monotonic() < deadline:
        time.sleep(0.5)
    pid = relaunch(command, cwd)
    _log(f"relaunched pid={pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
