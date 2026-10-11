from __future__ import annotations
from pathlib import Path

_ROOT_DIR = Path(__file__).parent.parent

BUILTIN_AGENTS_DIR = _ROOT_DIR / "components" / "agents" / "builtin"
CATALOG_AGENTS_DIR = _ROOT_DIR / "components" / "agents" / "catalog"

# Background task results handed back to Thrall's reasoning loop on completion
BACKGROUND_RESULT_MAX_CHARS = 12_000  # longer results are cut; the full text stays in the task result store
BACKGROUND_RESULT_HEADER = "[Background task finished — this is a system notice, not a message typed by the user]"
BACKGROUND_RESULT_INSTRUCTION = (
    "Tell the user the outcome now. Pass the result on in full unless it is very long; "
    "say plainly if the task failed or anything is missing."
)
