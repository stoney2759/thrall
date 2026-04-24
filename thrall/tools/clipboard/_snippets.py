from __future__ import annotations
import json
from pathlib import Path
from bootstrap import state

def _path() -> Path:
    base = state.get_workspace_dir() or "."
    p = Path(base).parent / "state" / "clipboard_snippets.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def load_all() -> dict[str, str]:
    p = _path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_all(snippets: dict[str, str]) -> None:
    _path().write_text(json.dumps(snippets, indent=2, ensure_ascii=False), encoding="utf-8")

def get(name: str) -> str | None:
    return load_all().get(name)

def save(name: str, content: str) -> None:
    snippets = load_all()
    snippets[name] = content
    save_all(snippets)

def delete(name: str) -> bool:
    snippets = load_all()
    if name not in snippets:
        return False
    del snippets[name]
    save_all(snippets)
    return True

def list_names() -> list[str]:
    return sorted(load_all().keys())
