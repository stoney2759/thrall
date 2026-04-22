from __future__ import annotations
import fnmatch
from pathlib import Path
from bootstrap import state

_DEFAULT_PROTECTED = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore"]


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


def is_protected(path: Path | str) -> bool:
    """Returns True if path matches a protected pattern.
    Protected paths are invisible to Thrall — treated as not found, not access denied.
    """
    name = Path(path).name
    return any(fnmatch.fnmatch(name, pat) for pat in _get_protected_patterns())


def filter_protected(paths: list[Path]) -> list[Path]:
    """Strip protected paths from a list — used by listing and search tools."""
    return [p for p in paths if not is_protected(p)]


def _get_protected_patterns() -> list[str]:
    try:
        return state.get_config().get("security", {}).get("protected_paths", _DEFAULT_PROTECTED)
    except Exception:
        return _DEFAULT_PROTECTED
