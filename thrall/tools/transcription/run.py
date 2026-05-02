from __future__ import annotations
import os
import time
from pathlib import Path
from uuid import UUID
from bootstrap import state
from schemas.tool import ToolCall, ToolResult


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    file_path = call.args.get("file_path", "").strip()
    language = call.args.get("language", "en")
    provider = call.args.get("provider") or None

    if not file_path:
        return _result(call.id, error="file_path is required", start=start)

    workspace_dir = state.get_workspace_dir()
    if workspace_dir and not os.path.isabs(file_path):
        file_path = os.path.join(workspace_dir, file_path)

    if not os.path.exists(file_path):
        return _result(call.id, error=f"file not found: {file_path}", start=start)

    audio_bytes = Path(file_path).read_bytes()
    filename = os.path.basename(file_path)

    from services.transcription.router import transcribe
    try:
        transcript = await transcribe(audio_bytes, filename=filename, language=language, provider=provider)
    except Exception as e:
        return _result(call.id, error=f"transcription failed: {e}", start=start)

    return _result(call.id, output=transcript, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "transcription_run"
DESCRIPTION = "Transcribe an audio file to text. Reads the file at the given path and returns the transcript. Supports mp3, wav, m4a, ogg, flac."
PARAMETERS = {
    "file_path": {
        "type": "string",
        "required": True,
        "description": "Path to the audio file. If relative, resolves against workspace.",
    },
    "language": {
        "type": "string",
        "required": False,
        "default": "en",
        "description": "BCP-47 language code (e.g. 'en', 'es', 'fr'). Default: 'en'.",
    },
    "provider": {
        "type": "string",
        "required": False,
        "description": "Override transcription provider: 'groq', 'openai', or 'openrouter'. Omit to use global config.",
    },
}
