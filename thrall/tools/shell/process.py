"""Run a command with a timeout that kills the whole process tree, not just the direct child.

subprocess.run(timeout=...) kills only the process it started, then waits for the output pipes to
close. A child it spawned (npx -> node, powershell -> anything) still holds those pipes open, so the
wait never ends and the tool hangs forever. Here the whole tree is killed first.
"""
from __future__ import annotations
import os
import signal
import subprocess
import sys
from constants.tools import SHELL_KILL_GRACE_SECONDS


def run_with_timeout(args: list[str] | str, shell: bool, cwd: str | None, timeout: int, env: dict) -> tuple[int, str, str]:
    """Returns (returncode, stdout, stderr). Raises subprocess.TimeoutExpired after killing the tree."""
    popen_kwargs: dict = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        args,
        shell=shell,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        cwd=cwd,
        env=env,
        **popen_kwargs,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc.pid)
        try:
            proc.communicate(timeout=SHELL_KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass  # a process outside the tree still holds the pipe — give up on the leftover output
        raise
    return proc.returncode, out or "", err or ""


def kill_tree(pid: int) -> None:
    """Kill a process and everything it started."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=SHELL_KILL_GRACE_SECONDS,
        )
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
