from __future__ import annotations
import os
import httpx
from bootstrap import state

_BASE_URL = "https://api.elevenlabs.io/v1"
_CHUNK_SIZE = 5000


def _cfg() -> dict:
    return state.get_config().get("tts", {}).get("elevenlabs", {})


_FORMAT_MAP = {
    "opus": "opus_48000_128",
    "mp3":  "mp3_44100_128",
    "wav":  "wav_44100",
    "pcm":  "pcm_44100",
}


async def synthesise(text: str, voice: str = "", output_format: str = "mp3_44100_128") -> bytes:
    output_format = _FORMAT_MAP.get(output_format, output_format)
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    cfg = _cfg()
    voice_id = voice or cfg.get("voice_id", "21m00Tcm4TlvDq8ikWAM")  # default: Rachel
    model_id = cfg.get("model", "eleven_monolingual_v1")
    stability = cfg.get("stability", 0.5)
    similarity_boost = cfg.get("similarity_boost", 0.75)

    chunks = _chunk_text(text)
    audio_parts = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for chunk in chunks:
            response = await client.post(
                f"{_BASE_URL}/text-to-speech/{voice_id}",
                headers={"xi-api-key": api_key, "Content-Type": "application/json"},
                params={"output_format": output_format},
                json={
                    "text": chunk,
                    "model_id": model_id,
                    "voice_settings": {"stability": stability, "similarity_boost": similarity_boost},
                },
            )
            if response.status_code != 200:
                try:
                    detail = response.json().get("detail", {}).get("message", response.text[:200])
                except Exception:
                    detail = response.text[:200]
                raise RuntimeError(f"ElevenLabs TTS error {response.status_code}: {detail}")
            audio_parts.append(response.content)

    return b"".join(audio_parts)


def estimate_cost(text: str) -> float:
    # ElevenLabs pay-as-you-go: ~$0.30 per 1000 chars
    return (len(text) / 1000) * 0.30


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
