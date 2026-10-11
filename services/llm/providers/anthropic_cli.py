from __future__ import annotations
from services.llm.providers.anthropic import AnthropicProvider
from services.auth import credentials


class AnthropicCliProvider(AnthropicProvider):
    """Anthropic provider that uses the local Claude CLI OAuth token.

    The CLI token (sk-ant-oat01-...) is an OAuth Bearer token, not an API key.
    Overrides _headers() to use Authorization: Bearer instead of x-api-key.
    """

    def __init__(self) -> None:
        token = credentials.get_token("anthropic") or ""
        super().__init__(api_key=token)

    def name(self) -> str:
        return "anthropic_cli"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
