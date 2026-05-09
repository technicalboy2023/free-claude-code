# CLAUDE.md — free-claude-code

> **For AI agents and developers.** This is the single source of truth for working in this repo.
> `AGENTS.md` mirrors this file exactly — keep them in sync on every change.

---

## QUICK CONTEXT

This repo is an **Anthropic-compatible proxy** written in Python 3.14 + FastAPI.  
It accepts Claude API calls and forwards them to: **NVIDIA NIM · OpenRouter · DeepSeek · Ollama**  
Optionally it runs a **Telegram / Discord bot** that drives the Claude CLI subprocess.

Entry point: `server.py` → `api/app.py:create_asgi_app()` → uvicorn

---

## ENVIRONMENT SETUP

```bash
# 1. Install uv (or update it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install Python 3.14
uv python install 3.14

# 3. Install dependencies
uv sync --frozen

# 4. Copy and fill env
cp .env.example .env
# Edit .env — at minimum set one provider API key + MODEL
```

Read `.env.example` for all environment variable documentation.

**Always use `uv run` to execute Python** — never the global `python` command.

---

## CI CHECKS (ALL MUST PASS BEFORE MERGE)

Run in this exact order:

```bash
uv run ruff format          # 1. Auto-format
uv run ruff check           # 2. Lint
uv run ty check             # 3. Type check (Python 3.14)
uv run pytest               # 4. Unit tests (deterministic, no live services)
```

**Rules:**
- Do NOT add `# type: ignore` or `# ty: ignore` — fix the underlying type issue
- All 4 checks are enforced in `.github/workflows/tests.yml` on push/merge
- Target formatter: `py314` (supports `except TypeError, ValueError:` without parens)
- Add tests for every new change, including edge cases

**Live smoke tests** (optional, requires real credentials):
```bash
FCC_LIVE_SMOKE=1 uv run pytest smoke/ -n 0
```

---

## ARCHITECTURE — DEPENDENCY DIRECTION

```
config/  ──► api/
config/  ──► providers/
config/  ──► messaging/
core/anthropic/  ──► api/
core/anthropic/  ──► providers/
core/anthropic/  ──► messaging/
providers/  ──► api/
api/  ──► cli/
api/  ──► messaging/
```

**Hard rules (enforced by `tests/contracts/test_import_boundaries.py`):**
- `core/` has zero imports from `api`, `messaging`, `cli`, `providers`, `config`, `smoke`
- `api/` may only import from `providers`: `base`, `exceptions`, `registry` (NOT per-adapter modules)
- `messaging/` does NOT import `api`, `cli`, or `smoke`
- Shared protocol helpers → `core/anthropic/` (not inside any provider)

---

## PACKAGE MAP

| Package | Owns |
|---------|------|
| `api/` | HTTP routes, request orchestration, model routing, auth, ASGI lifecycle |
| `providers/` | Provider adapters, stream conversion, rate limiting, error mapping |
| `messaging/` | Telegram/Discord adapters, CLI session orchestration, tree threading, session persistence |
| `cli/` | Claude CLI subprocess management, entrypoints |
| `config/` | Pydantic settings, provider catalog, NIM config, logging setup |
| `core/anthropic/` | SSE builders, stream contracts, token estimation, tool helpers, thinking parsers |
| `smoke/` | Optional live product smoke tests |
| `tests/` | Deterministic unit + contract tests |

---

## KEY KNOWN BUGS (Fix Before Next Release)

> These are tracked bugs from the last audit. Fix in priority order.

### BUG-01 — `api_url` uses `0.0.0.0` (BREAKS messaging)
**File:** `api/runtime.py:220`  
When `host = "0.0.0.0"`, the CLI manager gets `api_url = "http://0.0.0.0:8082/v1"` which is not routable.
```python
# FIX:
host_for_cli = "127.0.0.1" if self.settings.host in ("0.0.0.0", "::") else self.settings.host
api_url = f"http://{host_for_cli}:{self.settings.port}/v1"
```

### BUG-02 — Class-level `asyncio.Lock` in `MessagingRateLimiter`
**File:** `messaging/limiter.py:30`  
`_lock = asyncio.Lock()` at class body level → bound to wrong event loop under pytest.
Fix: Create lock lazily inside `get_instance()`.

### BUG-03 — SSE stream double-close
**File:** `providers/anthropic_messages.py` (error paths)  
Response `.aclose()` called twice in error + finally paths. Use single `try/finally` with `closed` guard.

### BUG-04 — Race in `MessagingRateLimiter` task compaction
**File:** `messaging/limiter.py:219-233`  
Futures orphaned when `enqueue` re-inserts same key between pop and execution.

### BUG-05 — `GlobalRateLimiter` scoped instances memory leak
**File:** `providers/rate_limit.py`  
`_scoped_instances` class var never cleaned between test registry creations.

### BUG-06 — `cancel_tree` captures stale task reference
**File:** `messaging/trees/queue_manager.py:545-555`  
`tree._current_task` read after `cancel_current_task()` may point to new task.


### BUG-08 — OpenAI client key mutation race under concurrent requests
**File:** `providers/openai_compat.py`  
`stream_response` mutates `self._client.api_key` without holding `_key_lock`.

---

## CODING STANDARDS

- **Simplicity first:** Write the smallest working code. No premature abstraction.
- **DRY:** Extract shared logic to `core/anthropic/`. Never copy-paste between providers.
- **Encapsulation:** Use `set_current_task()` etc. — do not access `_attributes` from outside the class.
- **Dead code:** Remove it. Use `settings.provider_type` not `"nvidia_nim"` literals.
- **Performance:** List accumulation for strings (not `+=` in loops). Cache env vars at init.
- **Platform-agnostic naming:** Use `PLATFORM_EDIT` not `TELEGRAM_EDIT` in shared code.
- **Complete migrations:** When moving modules, update all imports and remove old shims in the same PR.

---

## PROVIDER MODEL STRING FORMAT

```
MODEL="provider_id/model_name_path"

# Examples:
MODEL="nvidia_nim/meta/llama-3.1-8b-instruct"
MODEL="open_router/anthropic/claude-3.5-sonnet"
MODEL="deepseek/deepseek-chat"
MODEL="ollama/llama3"
```

Valid provider IDs: `nvidia_nim`, `open_router`, `deepseek`, `ollama`

---

## ADDING A NEW PROVIDER

1. Add `ProviderDescriptor` to `config/provider_catalog.py`
2. Add factory function + entry in `PROVIDER_FACTORIES` in `providers/registry.py`
3. Create `providers/<name>/` with a class extending `BaseProvider` (or `OpenAIChatTransport`/`AnthropicMessagesTransport`)
4. Update `SUPPORTED_PROVIDER_IDS` in `config/provider_ids.py` if needed
5. Add tests in `tests/providers/`
6. Run all CI checks

---

## COGNITIVE WORKFLOW FOR EVERY TASK

1. **READ** relevant files. Never guess at code structure.
2. **PLAN** the change. Identify root cause. Map all files that need updating.
3. **EXECUTE** incrementally. Fix root cause, not symptoms.
4. **VERIFY** by running CI checks and relevant smoke tests.
5. **DOCUMENT** in summary: `[Files Changed] [Logic Altered] [Verification Method] [Residual Risks]`

---

## DEPLOYMENT

**VPS / Linux:**
```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8082 --timeout-graceful-shutdown 5
```

**Systemd Service:**
For production 24/7 background execution, configure a `systemd` service executing the above `uv run` command.

**Health check:** `GET /health` → `{"status": "healthy"}`

---

## SMOKE TEST SKIP CLASSES (valid reasons to skip)

- `missing_env` — credentials, binaries, or opt-in flags absent
- `upstream_unavailable` — real provider or bot API unreachable

`product_failure` and `harness_bug` are **regressions**, not valid skips.