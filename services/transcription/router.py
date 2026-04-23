from __future__ import annotations
from bootstrap import state


async def transcribe(audio_bytes: bytes, filename: str = "audio.ogg", language: str = "en") -> str:
    cfg = state.get_config()
    provider = cfg.get("transcription", {}).get("provider", "groq").lower()

    if provider == "openai":
        from services.transcription.openai import transcribe as _transcribe
    elif provider == "openrouter":
        from services.transcription.openrouter import transcribe as _transcribe
    else:
        from services.transcription.groq import transcribe as _transcribe

    return await _transcribe(audio_bytes, filename=filename, language=language)
