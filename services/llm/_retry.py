from __future__ import annotations
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE = 5  # seconds — doubles each attempt: 5, 10, 20
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


async def post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict,
    json: dict,
    provider: str = "llm",
) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.post(url, headers=headers, json=json)
            if response.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BASE * (2 ** attempt)
                logger.warning(
                    f"{provider}: HTTP {response.status_code}, retrying in {wait}s "
                    f"(attempt {attempt + 1}/{_MAX_RETRIES})"
                )
                await asyncio.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == _MAX_RETRIES - 1:
                logger.error(f"{provider}: {type(e).__name__} after {_MAX_RETRIES} attempts")
                raise
            wait = _RETRY_BASE * (2 ** attempt)
            logger.warning(
                f"{provider}: {type(e).__name__}, retrying in {wait}s "
                f"(attempt {attempt + 1}/{_MAX_RETRIES})"
            )
            await asyncio.sleep(wait)
    response = await client.post(url, headers=headers, json=json)
    response.raise_for_status()
    return response
