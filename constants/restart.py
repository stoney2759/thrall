from __future__ import annotations

# thrall_restart — Thrall restarts itself (always asks the user first, even in trusted mode)
RESTART_DELAY_SECONDS = 8            # helper waits this long so the "restarting now" reply reaches the user
RESTART_KILL_WAIT_SECONDS = 15       # wait for the old processes to exit before relaunching
RESTART_PORT_WAIT_SECONDS = 20       # then wait for the webapp port to be free (thrall.py refuses a busy port)
RESTART_LOG_FILE = "logs/restart.log"  # the helper's own log (it outlives the Thrall process)
RESTART_ROOT_MARKER = "thrall.py"    # processes whose command line contains this belong to the Thrall tree
RESTART_DEFAULT_PORT = 8000
