MAX_TOOL_ITERATIONS = 30
AUTO_COMPACT_COOLDOWN_SECONDS = 300
MAX_TOOL_RESULT_IN_CONTEXT = 6_000  # chars — tool output is truncated to this before persisting in messages

# Mid-task messages — user messages that arrive while a task is running are queued
# and injected into the running reasoning loop instead of being refused.
MAX_PENDING_INTERJECTIONS = 10  # per session; oldest dropped beyond this
INTERJECTION_ACK = "Got it — I'll factor that in."
INTERJECTION_PREFIX = "[Message from the user, sent while you were working — take it into account before continuing]"

# Harness verify step — before a final reply, files written this turn must have been
# re-read afterwards, and a todo_write checklist used this turn must be fully done.
VERIFY_MAX_RETRIES = 1
VERIFY_WRITE_WORDS = frozenset({"write", "edit", "append", "save", "export"})
VERIFY_READ_WORDS = frozenset({"read", "cat", "stat", "open", "inspect", "ls", "info", "analyze", "find", "grep", "diff"})
VERIFY_PATH_ARGS = ("path", "file_path", "output_path", "dest", "destination")
