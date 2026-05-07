# Fix Implementation Plan
**Repo:** `free-claude-code`  
**Priority:** P1 (Critical) → P2 (High) → P3 (Medium)

---

## HOW TO USE THIS PLAN

Work through fixes top to bottom. After each fix:
1. Run `uv run ruff format && uv run ruff check && uv run ty check && uv run pytest`
2. Commit with message format: `fix(scope): description [BUG-XX]`

---

## P1 — CRITICAL FIXES (Do These First)

---

### FIX-01: `api_url` localhost bug [BUG-01]
**File:** `api/runtime.py`  
**Impact:** Messaging (Telegram/Discord) completely broken when `host = "0.0.0.0"`

**Change:**
```python
# BEFORE (line 220):
api_url = f"http://{self.settings.host}:{self.settings.port}/v1"

# AFTER:
_cli_host = (
    "127.0.0.1"
    if self.settings.host in ("0.0.0.0", "", "::", "[::]")
    else self.settings.host
)
api_url = f"http://{_cli_host}:{self.settings.port}/v1"
```

**Test to add:** `tests/api/test_runtime.py`
```python
def test_api_url_uses_localhost_for_wildcard_bind():
    from api.runtime import AppRuntime
    from unittest.mock import MagicMock, patch
    settings = MagicMock()
    settings.host = "0.0.0.0"
    settings.port = 8082
    # Verify the resolved URL is not 0.0.0.0
    # (test the internal helper once extracted)
```

**Verification:** Start server with default settings, enable messaging, confirm Claude CLI subprocess receives `http://127.0.0.1:8082/v1`.

---

### FIX-02: Class-level `asyncio.Lock` [BUG-02]
**File:** `messaging/limiter.py`

**Change:**
```python
# BEFORE (line 30):
class MessagingRateLimiter:
    _instance: MessagingRateLimiter | None = None
    _lock = asyncio.Lock()   # ← BUG: Created at import time

# AFTER:
class MessagingRateLimiter:
    _instance: MessagingRateLimiter | None = None
    _lock: asyncio.Lock | None = None

    @classmethod
    async def get_instance(
        cls,
        *,
        rate_limit: int = 1,
        rate_window: float = 1.0,
    ) -> MessagingRateLimiter:
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(rate_limit=rate_limit, rate_window=rate_window)
                cls._instance._start_worker()
        return cls._instance
```

**Also update `shutdown_instance`:**
```python
@classmethod
async def shutdown_instance(cls) -> None:
    if cls._lock is None:
        cls._lock = asyncio.Lock()
    async with cls._lock:
        instance = cls._instance
        cls._instance = None
    if instance is not None:
        await instance._shutdown_worker()
```

**Test to add:** `tests/messaging/test_limiter.py`
```python
import asyncio
import pytest

@pytest.mark.asyncio
async def test_get_instance_creates_fresh_lock_per_event_loop():
    from messaging.limiter import MessagingRateLimiter
    MessagingRateLimiter._instance = None
    MessagingRateLimiter._lock = None
    inst = await MessagingRateLimiter.get_instance(rate_limit=1, rate_window=1.0)
    assert inst is not None
    await MessagingRateLimiter.shutdown_instance()
```

---

### FIX-03: SSE stream double-close [BUG-03]
**File:** `providers/anthropic_messages.py`

**Principle:** Ensure `response.aclose()` is called exactly once using a guard flag.

**Change pattern:**
```python
# Wrap the stream body in a single try/finally:
async def stream_response(self, ...):
    response = None
    try:
        response = await self._client.post(...)
        response.raise_for_status()
        async for chunk in response.aiter_lines():
            yield chunk
    except httpx.HTTPStatusError as exc:
        # handle, then re-raise or yield error SSE — do NOT close here
        yield from self._error_sse(exc)
        raise
    finally:
        if response is not None:
            await response.aclose()
        # Clean up event_lines buffer
        event_lines: list[str] = []   # reset ref
```

**Verification:** Run `uv run pytest tests/providers/` and add a test that triggers an HTTP error mid-stream and asserts no `RuntimeError: response already closed` is raised.

---

### FIX-04: GlobalRateLimiter memory leak [BUG-05]
**File:** `providers/rate_limit.py`

**Change:** Add cleanup tracking + expose in test teardown.

```python
# In GlobalRateLimiter:
@classmethod
def cleanup_scoped_instances(cls) -> None:
    """Release all scoped rate limiter instances. Call on registry cleanup."""
    for instance in cls._scoped_instances.values():
        instance.close()   # or whatever cleanup method exists
    cls._scoped_instances.clear()
```

Ensure `cleanup_scoped_instances()` is called:
1. In `ProviderRegistry.cleanup()` (already done — verify it runs in tests)
2. In `conftest.py` teardown for test isolation

**Test to add:** `tests/providers/test_rate_limit.py`
```python
def test_cleanup_clears_scoped_instances():
    from providers.rate_limit import GlobalRateLimiter
    GlobalRateLimiter.get_scoped_instance("test_provider", ...)
    assert "test_provider" in GlobalRateLimiter._scoped_instances
    GlobalRateLimiter.cleanup_scoped_instances()
    assert len(GlobalRateLimiter._scoped_instances) == 0
```

---

## P2 — HIGH PRIORITY

---

### FIX-05: `render.yaml` default model [BUG-07]
**File:** `render.yaml`

**Change:**
```yaml
# BEFORE:
- key: MODEL
  value: "nvidia_nim/z-ai/glm4.7"

# AFTER:
- key: MODEL
  value: "nvidia_nim/meta/llama-3.1-8b-instruct"
  # Or check https://build.nvidia.com/explore/discover for current catalog
```

Also update `.env.example`:
```
MODEL="nvidia_nim/meta/llama-3.1-8b-instruct"
```

**Verification:** Fresh Render deploy with valid `NVIDIA_NIM_API_KEY` should pass startup model validation.

---

### FIX-06: OpenAI client key rotation race [BUG-08]
**File:** `providers/openai_compat.py`

The issue is that `self._client.api_key = ...` is mutated in `stream_response` without the `_key_lock`. Two options:

**Option A** (simpler) — Pass key via header override per-request, don't mutate shared client:
```python
async def stream_response(self, request, ...):
    async with self._global_rate_limiter:
        async with self._key_lock:
            api_key = self._next_api_key()
        # Pass key per-request via extra_headers instead of mutating self._client.api_key
        stream = await self._client.chat.completions.create(
            ...,
            extra_headers={"Authorization": f"Bearer {api_key}"},
        )
```

**Option B** — Always hold `_key_lock` during the full stream lifecycle (simpler but reduces concurrency).

Prefer **Option A** — doesn't serialize concurrent streams unnecessarily.

---

### FIX-07: `cancel_tree` stale task reference [BUG-06]
**File:** `messaging/trees/queue_manager.py`

**Change:** Have `cancel_current_task()` return the task it cancelled:
```python
# In MessageTree:
def cancel_current_task(self) -> asyncio.Task | None:
    """Cancel the current task and return it (or None if nothing was running)."""
    task = self._current_task
    if task is None or task.done():
        return None
    task.cancel()
    return task   # ← caller gets the exact task that was cancelled

# In TreeQueueManager.cancel_tree():
cancelled_task = tree.cancel_current_task()   # directly from return value
# No more tree._current_task access
```

---

### FIX-08: `_restore_tree_state` called before `platform.start()` [BUG-11]
**File:** `api/runtime.py`

**Change:** Reorder in `_start_message_handler`:
```python
# BEFORE:
self._restore_tree_state(session_store)
platform.on_message(self.message_handler.handle_message)
await platform.start()

# AFTER:
platform.on_message(self.message_handler.handle_message)
await platform.start()
self._restore_tree_state(session_store)   # ← after platform is live
```

---

## P3 — MEDIUM PRIORITY

---

### FIX-09: `get_settings()` test isolation [BUG-09]
**File:** `config/settings.py` + `tests/conftest.py`

**Change in `config/settings.py`:**
```python
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

def clear_settings_cache() -> None:
    """Clear the settings cache. Use in tests when env vars change."""
    get_settings.cache_clear()
```

**Change in `tests/conftest.py`:**
```python
import pytest
from config.settings import clear_settings_cache

@pytest.fixture(autouse=True)
def reset_settings_cache():
    yield
    clear_settings_cache()
```

---

### FIX-10: Dockerfile `HEALTHCHECK` [BUG-10]
**File:** `Dockerfile`

**Add after the `EXPOSE` line:**
```dockerfile
EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8082}/health || exit 1
```

Also add `curl` to the apt install (it may not be in `debian:bookworm-slim`):
```dockerfile
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
# (already present in Dockerfile — verify curl is installed)
```

---

### FIX-11: Claude CLI binary validation at startup [BUG-12]
**File:** `api/runtime.py` → `_start_message_handler`

**Add after `CLISessionManager` is constructed:**
```python
import shutil

cli_bin = self.settings.claude_cli_bin
if not shutil.which(cli_bin):
    logger.warning(
        "Claude CLI binary not found in PATH: bin={}. "
        "Messages will fail until it is installed. "
        "Install with: npm install -g @anthropic-ai/claude-code",
        cli_bin,
    )
```

---

### FIX-12: Token colon-stripping — add warning log [BUG-07]
**File:** `api/dependencies.py`

**Change:**
```python
if token and ":" in token:
    original = token
    token = token.split(":", 1)[0]
    logger.debug(
        "Auth token colon-stripped: original_len={} stripped_len={}",
        len(original),
        len(token),
    )
    if not token:
        raise HTTPException(status_code=401, detail="Invalid API key format")
```

---

## FUTURE-PROOF IMPROVEMENTS (Post-Bug-Fix)

These are enhancements, not bugs. Tackle after all P1/P2/P3 fixes are merged.

### FUTURE-01: Request correlation IDs
Generate a UUID per `/v1/messages` request and pass it through all downstream logs.
```python
import uuid
request_id = str(uuid.uuid4())[:8]
# Thread through logger context via loguru `contextvars` binding
```

### FUTURE-02: Provider health endpoint
```python
@router.get("/v1/providers/health")
async def provider_health(request: Request, settings=Depends(get_settings)):
    registry = request.app.state.provider_registry
    # Ping each configured provider and return status
```

### FUTURE-03: Prometheus metrics
Add `prometheus-fastapi-instrumentator` and expose `/metrics`. Track:
- Request count per provider
- Stream latency (p50, p95, p99)
- Provider error rate
- Rate limiter queue depth

### FUTURE-04: Config hot-reload on SIGHUP
```python
import signal
def _handle_sighup(sig, frame):
    clear_settings_cache()
    logger.info("Settings cache cleared via SIGHUP")
signal.signal(signal.SIGHUP, _handle_sighup)
```

### FUTURE-05: Anthropic pass-through provider
Add `anthropic` as a 5th provider that proxies directly to `api.anthropic.com`. Useful for rate-limit fronting with key rotation.

---

## COMMIT SEQUENCE

Suggested PR order to minimize merge conflicts:

1. `fix(config): default render.yaml model to valid NIM entry [BUG-07]`
2. `fix(runtime): use 127.0.0.1 for cli api_url when host is 0.0.0.0 [BUG-01]`
3. `fix(limiter): create asyncio.Lock lazily to avoid event loop binding [BUG-02]`
4. `fix(providers): guard SSE stream response against double-close [BUG-03]`
5. `fix(rate_limit): ensure GlobalRateLimiter scoped instances are cleaned up [BUG-05]`
6. `fix(queue_manager): return task from cancel_current_task to avoid stale ref [BUG-06]`
7. `fix(openai_compat): pass api key per-request instead of mutating shared client [BUG-08]`
8. `fix(runtime): restore tree state after platform.start() [BUG-11]`
9. `fix(settings): expose clear_settings_cache and use in conftest [BUG-09]`
10. `fix(docker): add HEALTHCHECK directive [BUG-10]`
11. `fix(runtime): warn on missing CLAUDE_CLI_BIN at messaging startup [BUG-12]`
12. `fix(auth): log warning when colon-stripping auth token [BUG-07-partial]`