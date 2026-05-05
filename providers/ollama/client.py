"""Ollama Cloud provider implementation using OpenAI-compatible API."""

from __future__ import annotations

from typing import Any

from loguru import logger

from providers.base import ProviderConfig
from providers.defaults import OLLAMA_DEFAULT_BASE
from providers.openai_compat import OpenAIChatTransport


class OllamaProvider(OpenAIChatTransport):
    """Ollama Cloud provider using the OpenAI-compatible chat completions API."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="OLLAMA",
            base_url=config.base_url or OLLAMA_DEFAULT_BASE,
            api_key=config.api_key or "ollama",
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build the OpenAI-compatible request body for Ollama."""
        from providers.nvidia_nim.request import build_request_body

        logger.debug(
            "OLLAMA_REQUEST: building request model={} msgs={}",
            getattr(request, "model", "?"),
            len(getattr(request, "messages", [])),
        )
        # Reuse NIM's OpenAI-compat request builder (thinking disabled for Ollama)
        from config.nim import NimSettings

        return build_request_body(
            request,
            NimSettings(),
            thinking_enabled=False,
        )
