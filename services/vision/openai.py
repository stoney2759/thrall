from __future__ import annotations
import base64
import os
import httpx
from bootstrap import state

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_VISION_MODEL = "google/gemini-2.5-flash"  # fallback if config missing


async def describe(image_bytes: bytes, media_type: str = "image/jpeg", prompt: str = "") -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    vision_cfg = state.get_config().get("vision", {})
    model = vision_cfg.get("model", _VISION_MODEL)
    max_tokens = int(vision_cfg.get("max_tokens", 1024))
    timeout = float(vision_cfg.get("timeout", 60))

    b64 = base64.b64encode(image_bytes).decode()
    user_prompt = prompt or "Describe this image in detail. If it contains text, transcribe it exactly."

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                ],
            }
        ],
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            _OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", response.text[:200])
        except Exception:
            detail = response.text[:200]
        raise RuntimeError(f"OpenRouter vision error {response.status_code}: {detail}")

    return response.json()["choices"][0]["message"]["content"].strip()
