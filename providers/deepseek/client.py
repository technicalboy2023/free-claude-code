"""DeepSeek provider implementation (native Anthropic-compatible Messages)."""

from __future__ import annotations

from typing import Any

import httpx

from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig
from providers.defaults import DEEPSEEK_ANTHROPIC_DEFAULT_BASE

from .request import build_request_body


class DeepSeekProvider(AnthropicMessagesTransport):
    """DeepSeek using ``https://api.deepseek.com/anthropic`` (Anthropic Messages API)."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="DEEPSEEK",
            default_base_url=DEEPSEEK_ANTHROPIC_DEFAULT_BASE,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        return build_request_body(
            request,
            thinking_enabled=self._is_thinking_enabled(request, thinking_enabled),
        )

    def _request_headers(self, *, api_key: str | None = None) -> dict[str, str]:
        key = api_key or self._api_key
        return {
            "Accept": "text/event-stream",
            "Content-Type": "application/json",
            "x-api-key": key,
        }

    async def _send_model_list_request(
        self, *, api_key: str | None = None
    ) -> httpx.Response:
        """DeepSeek lists models from the OpenAI-format root, not /anthropic."""
        url = str(
            httpx.URL(self._base_url).copy_with(
                path="/models", query=None, fragment=None
            )
        )
        return await self._client.get(
            url, headers=self._model_list_headers(api_key=api_key or self._api_key)
        )

    def _model_list_headers(self, *, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}
