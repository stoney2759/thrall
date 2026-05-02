from __future__ import annotations
import time
from pathlib import Path
from uuid import UUID
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    text = call.args.get("text", "").strip()
    voice = call.args.get("voice", "").strip()
    title = call.args.get("title", "").strip()
    confirmed = call.args.get("confirmed", False)

    if not text:
        return _result(call.id, error="text is required", start=start)

    from services.tts.router import needs_approval, cost_summary, synthesise
    from services.tts.storage import (
        is_cached, load_cache, save_cache, save_final,
        delete_chunks, should_keep_chunks, should_cache_short,
    )

    # Cost gate for long content
    if needs_approval(text) and not confirmed:
        summary = cost_summary(text)
        return _result(
            call.id,
            output=f"[approval required]\n{summary}\n\nCall again with confirmed=true to proceed.",
            start=start,
        )

    # Cache check
    if is_cached(text):
        cached = load_cache(text)
        path = _deliver_path(title or "thrall_audio", cached, ".mp3")
        return _result(call.id, output=f"[cached] {path}", start=start)

    try:
        audio_bytes = await synthesise(text, voice=voice)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)

    # Save
    if title:
        from services.tts.storage import save_final, save_chunk
        path = save_final(title, audio_bytes)
        if not should_keep_chunks():
            delete_chunks(title)
    else:
        path = save_cache(text, audio_bytes) if should_cache_short() else _deliver_path("thrall_audio", audio_bytes, ".mp3")
        if not should_cache_short():
            path.write_bytes(audio_bytes)

    return _result(call.id, output=str(path), start=start)


def _deliver_path(title: str, audio: bytes, ext: str) -> Path:
    from services.tts.storage import _audio_dir
    import time as _time
    p = _audio_dir() / f"{title}_{int(_time.time())}{ext}"
    p.write_bytes(audio)
    return p


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "audio_generate"
DESCRIPTION = (
    "Generate speech audio from text using the configured TTS provider. "
    "Returns the path to the saved audio file. For long content (books, documents) provide a title. "
    "Content over ~50 pages requires confirmed=true after seeing the cost estimate."
)
PARAMETERS = {
    "text":      {"type": "string",  "required": True},
    "voice":     {"type": "string",  "required": False, "default": ""},
    "title":     {"type": "string",  "required": False, "default": ""},
    "confirmed": {"type": "boolean", "required": False, "default": False},
}
