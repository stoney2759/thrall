from __future__ import annotations
import os
import httpx
from bootstrap import state

_URL = "https://api.openai.com/v1/audio/speech"
_CHUNK_SIZE = 4000  # OpenAI TTS max chars per request


def _cfg() -> dict:
    return state.get_config().get("tts", {}).get("openai", {})


async def synthesise(text: str, voice: str = "", output_format: str = "mp3") -> bytes:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    cfg = _cfg()
    model = cfg.get("model", "tts-1")
    voice = voice or cfg.get("voice", "onyx")
    speed = cfg.get("speed", 1.0)

    chunks = _chunk_text(text)
    audio_parts = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for chunk in chunks:
            response = await client.post(
                _URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "input": chunk, "voice": voice, "speed": speed, "response_format": output_format},
            )
            if response.status_code != 200:
                try:
                    detail = response.json().get("error", {}).get("message", response.text[:200])
                except Exception:
                    detail = response.text[:200]
                raise RuntimeError(f"OpenAI TTS error {response.status_code}: {detail}")
            audio_parts.append(response.content)

    return b"".join(audio_parts)


def estimate_cost(text: str) -> float:
    cfg = _cfg()
    model = cfg.get("model", "tts-1")
    rate = 30.0 if "hd" in model else 15.0  # $ per 1M chars
    return (len(text) / 1_000_000) * rate


def _chunk_text(text: str) -> list[str]:
    if len(text) <= _CHUNK_SIZE:
        return [text]
    chunks = []
    while text:
        if len(text) <= _CHUNK_SIZE:
            chunks.append(text)
            break
        split = text.rfind(" ", 0, _CHUNK_SIZE)
        if split == -1:
            split = _CHUNK_SIZE
        chunks.append(text[:split].strip())
        text = text[split:].strip()
    return chunks
