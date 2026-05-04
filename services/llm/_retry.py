from __future__ import annotations
import asyncio
import logging
import httpx

from constants.llm import MAX_RETRIES, RETRY_BASE_SECONDS, RETRYABLE_STATUS

logger = logging.getLogger(__name__)


async def post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict,
    json: dict,
    provider: str = "llm",
) -> httpx.Response:
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.post(url, headers=headers, json=json)
            if response.status_code in RETRYABLE_STATUS and attempt < MAX_RETRIES - 1:
                wait = RETRY_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    f"{provider}: HTTP {response.status_code}, retrying in {wait}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(wait)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(f"{provider}: {type(e).__name__} after {MAX_RETRIES} attempts")
                raise
            wait = RETRY_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                f"{provider}: {type(e).__name__}, retrying in {wait}s "
                f"(attempt {attempt + 1}/{MAX_RETRIES})"
            )
            await asyncio.sleep(wait)
    response = await client.post(url, headers=headers, json=json)
    response.raise_for_status()
    return response
