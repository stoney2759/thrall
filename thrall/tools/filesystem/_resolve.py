from __future__ import annotations
from pathlib import Path
from bootstrap import state


def resolve(path_str: str, fallback: str = ".") -> Path:
    """Resolve a path string.
    - Absolute paths pass through unchanged.
    - Relative paths anchor to workspace_dir from config.
    - Empty string falls back to workspace_dir (or '.' if not configured).
    """
    if not path_str:
        path_str = fallback

    p = Path(path_str)
    if p.is_absolute():
        return p

    workspace = state.get_workspace_dir()
    if workspace:
        return Path(workspace) / p

    return p
