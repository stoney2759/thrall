from __future__ import annotations
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_AUTH_FILE = Path(__file__).parent.parent.parent / "config" / "auth-profiles.json"
_ENV_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")

# In-memory snapshot — loaded at startup, swapped atomically on refresh
_snapshot: dict[str, dict] = {}


def load() -> None:
    """Load and resolve auth-profiles.json into the in-memory snapshot."""
    global _snapshot
    if not _AUTH_FILE.exists():
        logger.warning("auth-profiles.json not found — no credential profiles loaded")
        return
    try:
        raw = json.loads(_AUTH_FILE.read_text(encoding="utf-8"))
        resolved = {}
        for name, profile in raw.get("profiles", {}).items():
            resolved[name] = _resolve(profile)
        _snapshot = resolved
        logger.info("Credential profiles loaded: %s", list(_snapshot.keys()))
    except Exception as e:
        logger.error("Failed to load auth-profiles.json: %e", e)


def get(profile_name: str) -> dict | None:
    """Return resolved credential dict for a named profile, or None if missing."""
    return _snapshot.get(profile_name)


def get_token(profile_name: str) -> str | None:
    """
    Return the usable token/key string for a profile.
    Handles api_key, oauth (access_token), and cli_token types.
    """
    profile = get(profile_name)
    if not profile:
        return None
    kind = profile.get("type")
    if kind == "api_key":
        return profile.get("key") or None
    if kind == "oauth":
        token = profile.get("access_token", "")
        return token if token else None
    if kind == "cli_token":
        return _read_cli_token(profile.get("token_path", ""))
    return None


def write_oauth(profile_name: str, access_token: str, refresh_token: str, expires_at: int, account_id: str = "") -> None:
    """Persist an OAuth token into auth-profiles.json and refresh the snapshot."""
    if not _AUTH_FILE.exists():
        logger.error("auth-profiles.json not found — cannot write OAuth token")
        return
    try:
        raw = json.loads(_AUTH_FILE.read_text(encoding="utf-8"))
        profiles = raw.setdefault("profiles", {})
        profiles[profile_name] = {
            "type": "oauth",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "account_id": account_id,
        }
        tmp = str(_AUTH_FILE) + ".tmp"
        Path(tmp).write_text(json.dumps(raw, indent=2), encoding="utf-8")
        os.replace(tmp, _AUTH_FILE)
        _snapshot[profile_name] = profiles[profile_name]
        logger.info("OAuth token written for profile '%s'", profile_name)
    except Exception as e:
        logger.error("Failed to write OAuth token for '%s': %s", profile_name, e)


def _resolve(profile: dict) -> dict:
    """Resolve ${ENV_VAR} references in all string values."""
    out = {}
    for k, v in profile.items():
        if isinstance(v, str):
            out[k] = _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), v)
        else:
            out[k] = v
    return out


def _read_cli_token(token_path: str) -> str | None:
    """Read a token from a file path. Handles JSON files and plain text."""
    if not token_path:
        return None
    path = Path(os.path.expanduser(token_path))
    if not path.exists():
        logger.warning("CLI token file not found: %s", path)
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        # Try JSON first — Claude CLI and others store structured tokens
        try:
            data = json.loads(content)
            return (
                data.get("claudeAiOauth", {}).get("accessToken")
                or data.get("access_token")
                or data.get("token")
                or data.get("api_key")
                or None
            )
        except json.JSONDecodeError:
            # Plain text token
            return content if content else None
    except Exception as e:
        logger.error("Failed to read CLI token from %s: %s", path, e)
        return None
