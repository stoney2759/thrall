from __future__ import annotations
import hashlib
import time
from pathlib import Path
from bootstrap import state


def _cfg() -> dict:
    return state.get_config().get("tts", {})


def _audio_dir() -> Path:
    workspace = state.get_workspace_dir() or "."
    d = Path(workspace) / "audio"
    d.mkdir(exist_ok=True)
    return d


def _project_dir(title: str) -> Path:
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in title).strip()
    d = _audio_dir() / safe
    d.mkdir(exist_ok=True)
    (d / "data").mkdir(exist_ok=True)
    return d


def get_cache_path(text: str) -> Path:
    key = hashlib.sha256(text.encode()).hexdigest()[:16]
    return _audio_dir() / f"cache_{key}.mp3"


def is_cached(text: str) -> bool:
    return get_cache_path(text).exists()


def load_cache(text: str) -> bytes | None:
    p = get_cache_path(text)
    return p.read_bytes() if p.exists() else None


def save_cache(text: str, audio: bytes) -> Path:
    p = get_cache_path(text)
    p.write_bytes(audio)
    return p


def save_chunk(title: str, index: int, audio: bytes, ext: str = "mp3") -> Path:
    d = _project_dir(title)
    p = d / "data" / f"chunk_{index:03d}.{ext}"
    p.write_bytes(audio)
    return p


def save_final(title: str, audio: bytes, source_path: Path | None = None, ext: str = "mp3") -> Path:
    d = _project_dir(title)
    p = d / f"{title}.{ext}"
    p.write_bytes(audio)
    if source_path and source_path.exists() and source_path.parent != d:
        import shutil
        shutil.copy2(str(source_path), str(d / source_path.name))
    return p


def delete_chunks(title: str) -> int:
    d = _project_dir(title) / "data"
    count = 0
    for f in d.glob("chunk_*.mp3"):
        f.unlink()
        count += 1
    return count


def should_keep_chunks() -> bool:
    return _cfg().get("keep_chunks", True)


def should_cache_short() -> bool:
    return _cfg().get("cache_short_audio", True)
