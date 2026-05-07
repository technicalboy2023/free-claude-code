# Free Claude Code — Full Audit Report
**Repo:** `technicalboy2023/free-claude-code`  
**Date:** 2025-05  
**Auditor:** Claude (Deep Code Analysis)

---

## 1. WHAT THIS PROJECT IS

`free-claude-code` is a **FastAPI-based Anthropic-compatible proxy** that:
- Receives Claude API requests (`/v1/messages`, `/v1/models`, token count)
- Routes them to real AI providers: **NVIDIA NIM, OpenRouter, DeepSeek, Ollama**
- Optionally runs a **Telegram / Discord bot** that drives the Claude CLI subprocess
- Has optional **voice transcription** (local Whisper or NVIDIA Riva)
- Deploys on **Render** (Docker) or any VPS

**Tech Stack:** Python 3.14 · FastAPI · Pydantic v2 · httpx · loguru · python-telegram-bot · discord.py · uv

---

## 2. ARCHITECTURE OVERVIEW

```
Claude Code CLI / any client
        │  (Anthropic API format)
        ▼
  [server.py / GracefulLifespanApp]
        │
  [api/routes.py] ──► [api/services.py] ──► [api/model_router.py]
        │                                           │
        │                                   [providers/registry.py]
        │                                           │
        │               ┌───────────────────────────┤
        │               │           │               │
        │        NvidiaNim    OpenRouter      DeepSeek / Ollama
        │        (openai_compat)  (anthropic_messages)
        │
  [api/runtime.py] ──► [messaging/] ──► [cli/manager.py]
                          (Telegram/Discord bot → Claude CLI subprocess)
```

---

## 3. BUGS FOUND (PRIORITIZED)

### 🔴 CRITICAL

#### BUG-01 — `api_url` uses `0.0.0.0` → Messaging system self-calls fail
**File:** `api/runtime.py:220`
```python
# CURRENT (BROKEN when host = "0.0.0.0")
api_url = f"http://{self.settings.host}:{self.settings.port}/v1"
# → "http://0.0.0.0:8082/v1"  ← NOT routable
```
When `MESSAGING_PLATFORM=telegram` is set, the CLI manager uses `api_url` as the `ANTHROPIC_BASE_URL` for Claude CLI subprocess. `0.0.0.0` is a bind address, not a callable address. The subprocess will fail to connect.

**Fix:**
```python
host_for_cli = "127.0.0.1" if self.settings.host in ("0.0.0.0", "::") else self.settings.host
api_url = f"http://{host_for_cli}:{self.settings.port}/v1"
```

---

#### BUG-02 — Class-level `asyncio.Lock` in `MessagingRateLimiter`
**File:** `messaging/limiter.py:30`
```python
class MessagingRateLimiter:
    _lock = asyncio.Lock()   # ← Created at class definition / import time
```
`asyncio.Lock()` created at module-import level is bound to the event loop that exists at import time. Under pytest (which creates fresh event loops per test), this Lock can become "attached to a closed event loop" and raise `RuntimeError`. Also breaks if the proxy is restarted within the same process.

**Fix:**
```python
_lock: asyncio.Lock | None = None

@classmethod
async def get_instance(cls, ...) -> MessagingRateLimiter:
    if cls._lock is None:
        cls._lock = asyncio.Lock()
    async with cls._lock:
        ...
```

---

#### BUG-03 — SSE stream double-close / resource leak
**File:** `providers/anthropic_messages.py` (lines ~406, ~435)
In error paths, the response object can be `.aclose()`d twice — once in the error handler and once in the `finally` block. The second close is a no-op on some httpx versions but raises on others. Additionally `event_lines` buffer and `emitted_tracker` are not cleared on stream interruption, causing memory to accumulate on high-traffic instances.

**Fix:** Use a single `try/finally` pattern with a `closed` flag or wrap in an `AsyncExitStack`.

---

#### BUG-04 — Race condition in `MessagingRateLimiter` task compaction
**File:** `messaging/limiter.py:219-233`
The task compaction (dedup) logic pops `dedup_key` from `_queue_list` and `_queue_map` inside a `Condition` lock, but the actual task execution happens *outside* the lock. A concurrent `enqueue` call between pop and execute can re-insert the same key with a new entry, causing the old futures to be orphaned (their callbacks are never fired → caller awaits forever).

**Fix:** Resolve futures *inside* the condition lock, or use a dedicated per-key Future chain.

---

#### BUG-05 — `GlobalRateLimiter._scoped_instances` never cleaned up between requests
**File:** `providers/registry.py` + `providers/rate_limit.py`
`GlobalRateLimiter.cleanup_scoped_instances()` is called in `ProviderRegistry.cleanup()`, but the cleanup only runs on shutdown. During a long-running process, if providers are lazily created and discarded (test suites, dynamic provider changes), scoped instances accumulate in the class variable, causing a memory leak. Tests that create multiple registry instances will accumulate unbounded rate limiter state.

---

### 🟠 HIGH

#### BUG-06 — `cancel_tree` race: task reference captured after cancellation
**File:** `messaging/trees/queue_manager.py:545-555`
```python
if tree.cancel_current_task():
    ...
    cancelled_task = tree._current_task   # ← Direct internal access
```
`tree._current_task` can be replaced between `cancel_current_task()` returning and the attribute read (by the processor coroutine that picks the next queued item). `cancelled_task` then points to the *new* task, and the 1-second `wait_for` waits on the wrong task.

**Fix:** Have `cancel_current_task()` return the task object directly.

---

#### BUG-07 — Token colon-stripping truncates legitimate keys
**File:** `api/dependencies.py:118-120`
```python
if token and ":" in token:
    token = token.split(":", 1)[0]
```
This is meant to handle `token:model_name` formats sent by some clients, but silently truncates API keys that legitimately contain `:` (e.g., some service account tokens). No warning is logged. If the token prefix doesn't match the configured key, auth silently fails.

**Fix:** Add a log warning when colon-stripping is applied, and document which client formats trigger it.

---

#### BUG-08 — `render.yaml` default model `z-ai/glm4.7` likely invalid
**File:** `render.yaml:9`
```yaml
value: "nvidia_nim/z-ai/glm4.7"
```
This model path (`z-ai/glm4.7`) does not match standard NVIDIA NIM catalog entries. On first deploy with a valid `NVIDIA_NIM_API_KEY`, startup model validation (`validate_configured_models`) will call the NVIDIA API, fail to find `z-ai/glm4.7`, and **refuse to start**. New users will hit this immediately.

**Fix:** Change default to a well-known NIM model (e.g., `nvidia_nim/meta/llama-3.1-8b-instruct`) or add a comment instructing users to update.

---

### 🟡 MEDIUM

#### BUG-09 — `get_settings()` `lru_cache` breaks test isolation
**File:** `config/settings.py:last lines`
```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```
`lru_cache` on `get_settings` means settings are read once and never refreshed. Tests that patch env vars after import (e.g., via `monkeypatch.setenv`) will receive stale cached settings. The existing tests likely clear it manually in `conftest.py`, but this is a footgun.

**Fix:** Expose a `clear_settings_cache()` helper and call it in `conftest.py` teardown.

---

#### BUG-10 — Dockerfile missing `HEALTHCHECK` directive
**File:** `Dockerfile`
`render.yaml` defines `healthCheckPath: /health`, but the Dockerfile has no `HEALTHCHECK` instruction. Docker won't mark the container unhealthy if the server crashes silently. Render will only rely on the HTTP probe, which may not catch all failure modes.

**Fix:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8082/health || exit 1
```

---

#### BUG-11 — `_restore_tree_state` called before `platform.start()`
**File:** `api/runtime.py:_start_message_handler`
`_restore_tree_state(session_store)` runs before `await platform.start()`. If any restored node triggers an immediate callback (via `update_queue_positions` or `mark_node_processing`), those callbacks may attempt to send messages via the Telegram/Discord platform before the bot is connected.

**Fix:** Move `_restore_tree_state` to after `await platform.start()`.

---

#### BUG-12 — No `CLAUDE_CLI_BIN` validation at startup
**File:** `config/settings.py` / `api/runtime.py`
`CLAUDE_CLI_BIN` defaults to `"claude"` and is never validated at startup. If the Claude CLI is not installed or not in PATH, the server starts successfully but every Telegram/Discord message will silently fail when a subprocess is spawned.

**Fix:** At messaging startup, run `shutil.which(settings.claude_cli_bin)` and log a clear warning if missing.

---

#### BUG-13 — OpenAI client `api_key` mutation under concurrent requests
**File:** `providers/openai_compat.py`
```python
async with self._key_lock:
    self._client.api_key = self._next_api_key()
    payload = await self._client.models.list()
```
The `_key_lock` only covers `list_model_ids`. The `stream_response` path mutates `self._client.api_key` without holding `_key_lock`. Under high concurrency with key rotation, two coroutines can race and send requests with the wrong key.

**Fix:** Either acquire `_key_lock` in all paths that use the client, or create a new `AsyncOpenAI` instance per-request (passing the rotated key as an argument).

---

### 🔵 LOW / FUTURE-PROOF

#### BUG-14 — No structured logging correlation IDs
Requests have no request-ID propagation between the proxy layer and the upstream provider call. Debugging failures on multi-provider setups requires correlating by timestamp, which is imprecise.

**Fix:** Generate a `request_id` per `/v1/messages` request and thread it through logs.

---

#### BUG-15 — `CLAUDE.md` is a stub
**File:** `CLAUDE.md`
Current content: *"Ensure you've thoroughly reviewed the AGENTS.md file..."*  
For an AI-assisted development workflow, CLAUDE.md should be the authoritative guide. Currently it delegates everything to AGENTS.md (which is identical to itself). This is confusing duplication.

---

## 4. SECURITY AUDIT

| Area | Status | Notes |
|------|--------|-------|
| Auth token comparison | ✅ Good | Uses `secrets.compare_digest` (constant-time, CWE-208 safe) |
| Non-root Docker user | ✅ Good | `appuser` (uid 1000) |
| SSRF via web_fetch | ⚠️ Configurable | Disabled by default; private networks blocked by setting |
| API key in logs | ✅ Safe | Logs only metadata when `LOG_RAW_API_PAYLOADS=false` |
| `.env` in Docker | ✅ Good | `.env.example` copied, not `.env` |
| Colon token stripping | ⚠️ Silent | Can silently truncate valid tokens (BUG-07) |
| render.yaml `generateValue` | ✅ Good | Auto-generates `ANTHROPIC_AUTH_TOKEN` if not provided |

---

## 5. PERFORMANCE AUDIT

| Area | Status | Notes |
|------|--------|-------|
| Provider HTTP clients | ✅ Pooled | `httpx.AsyncClient` reused per provider instance |
| Rate limiting | ✅ Scoped | Per-provider `GlobalRateLimiter` with concurrency cap |
| Model list caching | ✅ Warm | Background task caches model lists after startup |
| Settings | ⚠️ lru_cache | Cached forever, no refresh path (BUG-09) |
| String concat in loops | ✅ OK | Uses list accumulation in SSE builders |
| Key rotation | ✅ Round-robin | `KeyRotator` handles multi-key load distribution |

---

## 6. TEST COVERAGE GAPS

- `messaging/limiter.py` — race conditions untested under concurrent load
- `api/runtime.py:_restore_tree_state` — no test for post-restore callback ordering
- `providers/openai_compat.py` — key rotation under concurrent `stream_response` untested
- `api/dependencies.py` — colon-stripping edge cases (empty token after strip) missing tests
- Integration test for `MESSAGING_PLATFORM=telegram` startup with `0.0.0.0` host missing

---

## 7. FUTURE-PROOFING RECOMMENDATIONS

1. **Add Anthropic provider** — Currently only 3rd-party providers. Adding `anthropic` as a pass-through provider would make the proxy useful for rate-limit fronting.
2. **Structured telemetry** — Add OpenTelemetry traces for request → provider → response spans.
3. **Provider health checks** — Periodic background pings to verify provider reachability; surface in `/health`.
4. **Multi-tenant auth** — Current auth is single-token. A key-per-user model would support multi-user deployments.
5. **Config hot-reload** — Clear `lru_cache` on SIGHUP to allow env var changes without restart.
6. **Streaming backpressure** — Add flow control between the SSE response and the upstream stream to avoid buffering unbounded data.
7. **Metrics endpoint** — `/metrics` (Prometheus format) for request counts, latency, provider errors.