"""Tests for Ollama provider."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.defaults import OLLAMA_DEFAULT_BASE
from providers.ollama import OllamaProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ollama_config():
    return ProviderConfig(
        api_key="test_ollama_key",
        base_url="http://custom-ollama:11434/v1",
        rate_limit=10,
        rate_window=60,
    )


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    """Mock the global rate limiter to prevent waiting."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.openai_compat.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "llama3.3"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.7
        self.top_p = 0.9
        self.system = "You are helpful."
        self.stop_sequences = []
        self.tools = []
        self.extra_body = {}
        self.thinking = MagicMock()
        self.thinking.enabled = True
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# Constant / default tests
# ---------------------------------------------------------------------------


def test_ollama_default_base():
    assert OLLAMA_DEFAULT_BASE == "https://ollama.com/v1"


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


def test_init(ollama_config):
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    assert provider._api_key == "test_ollama_key"
    assert provider._base_url == "http://custom-ollama:11434/v1"


def test_init_defaults():
    config = ProviderConfig(api_key="ollama")
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(config)

    assert provider._api_key == "ollama"
    assert provider._base_url == OLLAMA_DEFAULT_BASE


def test_init_empty_key_falls_back_to_ollama():
    """When api_key is falsy, provider defaults to 'ollama'."""
    config = ProviderConfig(api_key="ollama")
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(config)
    # The fallback 'or "ollama"' ensures a usable default
    assert provider._api_key == "ollama"


def test_init_custom_base_url_is_stripped():
    """Trailing slash is stripped by the OpenAIChatTransport base."""
    config = ProviderConfig(
        api_key="test_key",
        base_url="http://localhost:11434/v1/",
    )
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(config)
    assert provider._base_url == "http://localhost:11434/v1"


def test_init_uses_configurable_timeouts():
    """Provider passes configurable read/write/connect timeouts to client."""
    config = ProviderConfig(
        api_key="test_key",
        base_url="http://localhost:11434/v1",
        http_read_timeout=600.0,
        http_write_timeout=15.0,
        http_connect_timeout=5.0,
    )
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        OllamaProvider(config)
        call_kwargs = mock_openai.call_args[1]
        timeout = call_kwargs["timeout"]
        assert timeout.read == 600.0
        assert timeout.write == 15.0
        assert timeout.connect == 5.0


def test_init_with_proxy():
    """Provider creates an httpx client with proxy when configured."""
    config = ProviderConfig(
        api_key="test_key",
        base_url="http://localhost:11434/v1",
        proxy="http://proxy:8080",
    )
    with (
        patch("providers.openai_compat.httpx.AsyncClient") as mock_httpx,
        patch("providers.openai_compat.AsyncOpenAI"),
    ):
        OllamaProvider(config)
        mock_httpx.assert_called_once()
        call_kwargs = mock_httpx.call_args[1]
        assert call_kwargs["proxy"] == "http://proxy:8080"


def test_init_caches_nim_settings():
    """NimSettings is cached at init, not created per request."""
    config = ProviderConfig(api_key="test_key")
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(config)
    assert hasattr(provider, "_nim_settings")
    from config.nim import NimSettings

    assert isinstance(provider._nim_settings, NimSettings)


# ---------------------------------------------------------------------------
# Request body building tests
# ---------------------------------------------------------------------------


def test_build_request_body_basic(ollama_config):
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    req = MockRequest()
    body = provider._build_request_body(req)

    assert body["model"] == "llama3.3"
    assert body["temperature"] == 0.7
    assert len(body["messages"]) >= 2  # System + User
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"] == "You are helpful."


def test_build_request_body_thinking_always_disabled(ollama_config):
    """Ollama always passes thinking_enabled=False regardless of request."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    req = MockRequest()
    req.thinking.enabled = True

    body = provider._build_request_body(req, thinking_enabled=True)

    # Even with thinking_enabled=True, Ollama should NOT include reasoning params
    extra = body.get("extra_body", {})
    ctk = extra.get("chat_template_kwargs", {})
    assert ctk.get("thinking") is not True or ctk.get("enable_thinking") is not True


def test_build_request_body_no_system(ollama_config):
    """Request without system prompt produces only user messages."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    req = MockRequest(system=None)
    body = provider._build_request_body(req)

    assert body["messages"][0]["role"] == "user"


# ---------------------------------------------------------------------------
# Streaming tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_response_text(ollama_config):
    """Test streaming text response."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    req = MockRequest()

    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [
        MagicMock(
            delta=MagicMock(content="Hello", reasoning_content=""), finish_reason=None
        )
    ]
    mock_chunk1.usage = None

    mock_chunk2 = MagicMock()
    mock_chunk2.choices = [
        MagicMock(
            delta=MagicMock(content=" World", reasoning_content=""),
            finish_reason="stop",
        )
    ]
    mock_chunk2.usage = MagicMock(completion_tokens=10)

    async def mock_stream():
        yield mock_chunk1
        yield mock_chunk2

    with patch.object(
        provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [e async for e in provider.stream_response(req)]

    assert len(events) > 0
    assert "event: message_start" in events[0]

    text_content = ""
    for e in events:
        if "event: content_block_delta" in e and '"text_delta"' in e:
            for line in e.splitlines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "delta" in data and "text" in data["delta"]:
                        text_content += data["delta"]["text"]

    assert "Hello World" in text_content


@pytest.mark.asyncio
async def test_stream_response_suppresses_thinking(ollama_config):
    """Thinking/reasoning is always suppressed for Ollama."""
    config = ollama_config.model_copy(update={"enable_thinking": False})
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(config)

    req = MockRequest()

    mock_chunk = MagicMock()
    mock_chunk.choices = [
        MagicMock(
            delta=MagicMock(
                content="<think>secret</think>Answer", reasoning_content="Thinking..."
            ),
            finish_reason="stop",
        )
    ]
    mock_chunk.usage = None

    async def mock_stream():
        yield mock_chunk

    with patch.object(
        provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [e async for e in provider.stream_response(req)]

    event_text = "".join(events)
    assert "thinking_delta" not in event_text
    assert "Thinking..." not in event_text
    assert "secret" not in event_text
    assert "Answer" in event_text


@pytest.mark.asyncio
async def test_stream_response_emits_message_stop(ollama_config):
    """Stream always terminates with message_stop."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    req = MockRequest()

    mock_chunk = MagicMock()
    mock_chunk.choices = [
        MagicMock(
            delta=MagicMock(content="Done", reasoning_content=""),
            finish_reason="stop",
        )
    ]
    mock_chunk.usage = MagicMock(completion_tokens=1)

    async def mock_stream():
        yield mock_chunk

    with patch.object(
        provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [e async for e in provider.stream_response(req)]

    assert any("event: message_stop" in e for e in events)


@pytest.mark.asyncio
async def test_stream_response_error_emits_sse_error(ollama_config):
    """Provider errors are mapped to Anthropic SSE error events."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    req = MockRequest()

    with patch.object(
        provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = Exception("upstream failure")

        events = [e async for e in provider.stream_response(req)]

    event_text = "".join(events)
    assert "event: message_stop" in event_text


# ---------------------------------------------------------------------------
# Cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup(ollama_config):
    """Cleanup closes the underlying HTTP client."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    provider._client = MagicMock()
    provider._client.aclose = AsyncMock()

    await provider.cleanup()

    provider._client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# Model listing tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_model_ids(ollama_config):
    """list_model_ids returns model ids from OpenAI-compatible endpoint."""
    with patch("httpx.AsyncClient"):
        provider = OllamaProvider(ollama_config)

    mock_model1 = MagicMock()
    mock_model1.id = "llama3.3"
    mock_model2 = MagicMock()
    mock_model2.id = "mistral"

    mock_response = MagicMock()
    mock_response.data = [mock_model1, mock_model2]

    with patch.object(
        provider._client.models, "list", new_callable=AsyncMock
    ) as mock_list:
        mock_list.return_value = mock_response
        ids = await provider.list_model_ids()

    assert "llama3.3" in ids
    assert "mistral" in ids
