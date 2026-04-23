from __future__ import annotations
import os
import httpx

_URL = "https://api.openai.com/v1/audio/transcriptions"
_MODEL = "whisper-1"


async def transcribe(audio_bytes: bytes, filename: str = "audio.ogg", language: str = "en") -> str:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            _URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_bytes, "application/octet-stream")},
            data={"model": _MODEL, "language": language, "response_format": "json"},
        )

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", response.text[:200])
        except Exception:
            detail = response.text[:200]
        raise RuntimeError(f"OpenAI API error {response.status_code}: {detail}")

    return response.json().get("text", "").strip()
