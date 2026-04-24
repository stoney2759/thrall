from __future__ import annotations
from bootstrap import state

_COST_THRESHOLD = 150_000  # chars — approx 50 pages


def _cfg() -> dict:
    return state.get_config().get("tts", {})


async def synthesise(text: str, voice: str = "", output_format: str = "") -> bytes:
    provider = _cfg().get("provider", "openai").lower()

    if provider == "elevenlabs":
        from services.tts.providers.elevenlabs import synthesise as _synth
        fmt = output_format or "mp3_44100_128"
    else:
        from services.tts.providers.openai import synthesise as _synth
        fmt = output_format or "mp3"

    return await _synth(text, voice=voice, output_format=fmt)


def estimate_cost(text: str) -> float:
    provider = _cfg().get("provider", "openai").lower()
    if provider == "elevenlabs":
        from services.tts.providers.elevenlabs import estimate_cost
    else:
        from services.tts.providers.openai import estimate_cost
    return estimate_cost(text)


def needs_approval(text: str) -> bool:
    return len(text) > _COST_THRESHOLD


def cost_summary(text: str) -> str:
    chars = len(text)
    cost = estimate_cost(text)
    provider = _cfg().get("provider", "openai")
    pages = chars // 3000
    return f"~{pages} pages | {chars:,} characters | estimated cost: ${cost:.2f} ({provider})"
