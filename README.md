<div align="center">

# 🤖 Free Claude Code

Use Claude Code CLI, VS Code, JetBrains ACP, or chat bots through your own Anthropic-compatible proxy.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python 3.14](https://img.shields.io/badge/python-3.14-3776ab.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json&style=for-the-badge)](https://github.com/astral-sh/uv)
[![Tested with Pytest](https://img.shields.io/badge/testing-Pytest-00c0ff.svg?style=for-the-badge)](https://github.com/technicalboy2023/free-claude-code/actions/workflows/tests.yml)
[![Type checking: Ty](https://img.shields.io/badge/type%20checking-ty-ffcc00.svg?style=for-the-badge)](https://pypi.org/project/ty/)
[![Code style: Ruff](https://img.shields.io/badge/code%20formatting-ruff-f5a623.svg?style=for-the-badge)](https://github.com/astral-sh/ruff)
[![Logging: Loguru](https://img.shields.io/badge/logging-loguru-4ecdc4.svg?style=for-the-badge)](https://github.com/Delgan/loguru)

Free Claude Code routes Anthropic Messages API traffic from Claude Code to NVIDIA NIM, OpenRouter, DeepSeek, or Ollama Cloud — with **round-robin API key rotation** for rate-limit resilience. It keeps Claude Code's client-side protocol stable while letting you choose free or paid models.

[Deployment & Setup](#deployment--setup-vps-recommended) · [Providers](#choose-a-provider) · [Key Rotation](#round-robin-key-rotation) · [Clients](#connect-claude-code) · [Development](#development)

</div>

<div align="center">
  <img src="pic.png" alt="Free Claude Code in action" width="700">
</div>

## What You Get

- **Drop-in proxy** for Claude Code's Anthropic API calls.
- **Four cloud providers**: NVIDIA NIM, OpenRouter, DeepSeek, and Ollama Cloud.
- **Round-robin key rotation**: distribute requests across multiple API keys per provider.
- **Per-model routing**: send Opus, Sonnet, Haiku, and fallback traffic to different providers.
- **Native model picker**: Claude Code's `/model` command discovers all available models.
- **Streaming, tool use, reasoning/thinking** block handling, and local request optimizations.
- **Optional Discord or Telegram bot** wrapper for remote coding sessions.
- **Optional voice-note transcription** through local Whisper or NVIDIA NIM.
- **Render-ready**: Dockerfile and `render.yaml` included for one-click cloud deploy.

## Deployment & Setup (Production Recommended)

We highly recommend deploying Free Claude Code using `systemd` for maximum stability, 24/7 uptime, and seamless background execution. This setup runs completely in user-space (no root required for the proxy).

### 1. Install Dependencies

Install `uv` (the lightning-fast Python package manager) and Python 3.14:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.bashrc

# Install Python 3.14 via uv
uv python install 3.14
```

### 2. Clone and Configure

Clone the repository and set up your environment variables:

```bash
git clone https://github.com/technicalboy2023/free-claude-code.git
cd free-claude-code
cp .env.example .env
```

Edit your `.env` file to set your provider API keys and authentication token:

```bash
nano .env
```

*Ensure you set `ANTHROPIC_AUTH_TOKEN="your_secure_password"` and at least one provider key (e.g., `NVIDIA_NIM_API_KEY`).*

### 3. Test the Server Manually

Before setting up auto-start, verify that the server runs correctly:

```bash
uv run uvicorn server:app --host 0.0.0.0 --port 8082
```
*If it starts without errors, press `CTRL+C` to stop it and proceed to the next step.*

### 4. Setup Auto-Start (Background Mode)

To keep the proxy running permanently in the background and auto-start on PC reboot, create a **user-level systemd service**:

```bash
mkdir -p ~/.config/systemd/user
nano ~/.config/systemd/user/free-claude-code.service
```

Paste the following configuration (replace `/home/yourusername` with your actual home directory path):

```ini
[Unit]
Description=Free Claude Code Proxy Server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/yourusername/Desktop/my project/free-claude-code
ExecStart=/home/yourusername/.local/bin/uv run uvicorn server:app --host 0.0.0.0 --port 8082
Restart=always
RestartSec=5
Environment=PATH=/home/yourusername/.local/bin:/usr/local/bin:/usr/bin:/bin

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

Enable and start the service:

```bash
systemctl --user daemon-reload
systemctl --user enable --now free-claude-code.service

# (Optional) Allow the service to run even when you are not logged in:
loginctl enable-linger $USER
```

### 5. Service Management & Updates

**Check Status & Logs:**
```bash
# Check if the service is running
systemctl --user status free-claude-code.service

# View live proxy logs
journalctl --user -u free-claude-code.service -f
```

**Stop / Start / Restart Service:**
```bash
systemctl --user stop free-claude-code.service
systemctl --user start free-claude-code.service
systemctl --user restart free-claude-code.service
```

**How to Update to the Latest Code:**
Whenever a new update is released, you can seamlessly update without breaking the setup:
```bash
cd ~/free-claude-code
git pull
uv sync --frozen
systemctl --user restart free-claude-code.service
```


## Choose A Provider

**How to switch models:** To change your AI model, you only need to edit the `MODEL` variable in your `.env` file (or your Render Environment Variables). The router will automatically detect the change. You do **not** need to edit any other files. Just make sure the corresponding provider's API key is also set.

Model values must use this format:

```text
provider_id/model/name
```

`MODEL` is the fallback. `MODEL_OPUS`, `MODEL_SONNET`, and `MODEL_HAIKU` override routing for requests that Claude Code sends for those tiers.

| Provider | Prefix | Transport | Key | Default Base URL |
| --- | --- | --- | --- | --- |
| <img src="https://cdn.simpleicons.org/nvidia/76B900" alt="" width="18" height="18"> NVIDIA NIM | `nvidia_nim/...` | OpenAI chat translation | `NVIDIA_NIM_API_KEY` | `https://integrate.api.nvidia.com/v1` |
| <img src="https://cdn.simpleicons.org/openrouter/6C47FF" alt="" width="18" height="18"> OpenRouter | `open_router/...` | Anthropic Messages | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| <img src="https://cdn.simpleicons.org/deepseek/4D6BFF" alt="" width="18" height="18"> DeepSeek | `deepseek/...` | Anthropic Messages | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/anthropic` |
| <img src="https://cdn.simpleicons.org/ollama/000000" alt="" width="18" height="18"> Ollama Cloud | `ollama/...` | OpenAI chat translation | `OLLAMA_API_KEY` | `https://ollama.com/v1` |

<details>
<summary><img src="https://cdn.simpleicons.org/nvidia/76B900" alt="" width="18" height="18"> <b>NVIDIA NIM</b></summary>

Get a key at [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys).

```dotenv
NVIDIA_NIM_API_KEY="nvapi-your-key"
MODEL="nvidia_nim/meta/llama-3.1-8b-instruct"
```

Popular models:

- `nvidia_nim/meta/llama-3.1-8b-instruct`
- `nvidia_nim/z-ai/glm5`
- `nvidia_nim/moonshotai/kimi-k2.5`
- `nvidia_nim/minimaxai/minimax-m2.5`

Browse models at [build.nvidia.com](https://build.nvidia.com/explore/discover).

</details>

<details>
<summary><img src="https://cdn.simpleicons.org/openrouter/6C47FF" alt="" width="18" height="18"> <b>OpenRouter</b></summary>

Get a key at [openrouter.ai/keys](https://openrouter.ai/keys).

```dotenv
OPENROUTER_API_KEY="sk-or-your-key"
MODEL="open_router/stepfun/step-3.5-flash:free"
```

Browse [all models](https://openrouter.ai/models) or [free models](https://openrouter.ai/collections/free-models).

</details>

<details>
<summary><img src="https://cdn.simpleicons.org/deepseek/4D6BFF" alt="" width="18" height="18"> <b>DeepSeek</b></summary>

Get a key at [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys).

```dotenv
DEEPSEEK_API_KEY="your-deepseek-key"
MODEL="deepseek/deepseek-chat"
```

This provider uses DeepSeek's Anthropic-compatible endpoint, not the OpenAI chat-completions endpoint.

</details>

<details>
<summary><img src="https://cdn.simpleicons.org/ollama/000000" alt="" width="18" height="18"> <b>Ollama Cloud</b></summary>

Get a key at [ollama.com](https://ollama.com).

```dotenv
OLLAMA_API_KEY="your-ollama-key"
MODEL="ollama/llama3.3"
```

This provider uses Ollama's OpenAI-compatible endpoint.

</details>

<details>
<summary><b>Mix providers by model tier</b></summary>

Each tier can use a different provider:

```dotenv
NVIDIA_NIM_API_KEY="nvapi-your-key"
OPENROUTER_API_KEY="sk-or-your-key"

MODEL_OPUS="nvidia_nim/moonshotai/kimi-k2.5"
MODEL_SONNET="open_router/deepseek/deepseek-r1-0528:free"
MODEL_HAIKU="deepseek/deepseek-chat"
MODEL="nvidia_nim/meta/llama-3.1-8b-instruct"
```

</details>

## Round-Robin Key Rotation

Distribute requests across multiple API keys to avoid per-key rate limits. Set comma-separated keys in `.env`:

```dotenv
# Single key (default)
NVIDIA_NIM_API_KEY="nvapi-key1"

# Multiple keys — requests cycle through each key in order
NVIDIA_NIM_API_KEY="nvapi-key1,nvapi-key2,nvapi-key3"
OPENROUTER_API_KEY="sk-or-v1-key1,sk-or-v1-key2"
DEEPSEEK_API_KEY="sk-ds-key1,sk-ds-key2"
OLLAMA_API_KEY="key1,key2"
```

**How it works:**

- Each provider creates a thread-safe `KeyRotator` on startup.
- Every request rotates to the next key in round-robin order.
- Keys are deduplicated and whitespace-trimmed automatically.
- Single-key setups work exactly as before — no config change needed.

## Connect Claude Code

### Claude Code CLI

On your local machine (Windows/Mac), configure the Claude Code CLI to route traffic to your new VPS:

```bash
claude config set customBaseUrl http://<YOUR_VPS_PUBLIC_IP>:8082
claude config set customApiKey your_secure_password
```

Now, simply type `claude` in your local terminal.

### VS Code Extension

Open Settings, search for `claude-code.environmentVariables`, choose **Edit in settings.json**, and add:

```json
"claudeCode.environmentVariables": [
  { "name": "ANTHROPIC_BASE_URL", "value": "http://<YOUR_VPS_PUBLIC_IP>:8082" },
  { "name": "ANTHROPIC_AUTH_TOKEN", "value": "your_secure_password" }
]
```

Reload the extension. If the extension shows a login screen, choose the Anthropic Console path once; the local proxy still handles model traffic after the environment variables are active.

### JetBrains ACP

Edit the installed Claude ACP config:

- Windows: `C:\Users\%USERNAME%\AppData\Roaming\JetBrains\acp-agents\installed.json`
- Linux/macOS: `~/.jetbrains/acp.json`

Set the environment for `acp.registry.claude-acp`:

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://<YOUR_VPS_PUBLIC_IP>:8082",
  "ANTHROPIC_AUTH_TOKEN": "your_secure_password"
}
```

Restart the IDE after changing the file.

### Model Picker

Claude Code 2.1.126 or later reads this proxy's `/v1/models` endpoint when `ANTHROPIC_BASE_URL` points at the proxy. Start Claude Code normally, run `/model`, and choose any discovered provider model.

<div align="center">
  <img src="cc-model-picker.png" alt="Claude Code model picker showing gateway models" width="700">
</div>

The proxy lists models for configured provider keys. Picker-safe IDs are routed back to the real provider/model automatically, so no `.env` edit or separate launcher script is needed after startup.

Each provider model also has a `(no thinking)` picker variant. Use it when a model does not support Claude Code thinking or fails with adaptive-thinking requests.

## Optional Integrations

### Discord And Telegram Bots

The bot wrapper runs Claude Code sessions remotely, streams progress, supports reply-based conversation branches, and can stop or clear tasks.

Discord minimum config:

```dotenv
MESSAGING_PLATFORM="discord"
DISCORD_BOT_TOKEN="your-discord-bot-token"
ALLOWED_DISCORD_CHANNELS="123456789"
CLAUDE_WORKSPACE="./agent_workspace"
ALLOWED_DIR="C:/Users/yourname/projects"
```

Create the bot in the [Discord Developer Portal](https://discord.com/developers/applications), enable Message Content Intent, and invite it with read/send/history permissions.

Telegram minimum config:

```dotenv
MESSAGING_PLATFORM="telegram"
TELEGRAM_BOT_TOKEN="123456789:ABC..."
ALLOWED_TELEGRAM_USER_ID="your-user-id"
CLAUDE_WORKSPACE="./agent_workspace"
ALLOWED_DIR="C:/Users/yourname/projects"
```

Get a token from [@BotFather](https://t.me/BotFather) and your user ID from [@userinfobot](https://t.me/userinfobot).

Useful commands:

- `/stop` cancels a task; reply to a task message to stop only that branch.
- `/clear` resets sessions; reply to clear one branch.
- `/stats` shows session state.

### Voice Notes

Voice notes work on Discord and Telegram. Choose one backend:

```bash
uv sync --extra voice_local
uv sync --extra voice
uv sync --extra voice --extra voice_local
```

```dotenv
VOICE_NOTE_ENABLED=true
WHISPER_DEVICE="cpu"          # cpu | cuda | nvidia_nim
WHISPER_MODEL="base"
HF_TOKEN=""
```

Use `WHISPER_DEVICE="nvidia_nim"` with the `voice` extra and `NVIDIA_NIM_API_KEY` for NVIDIA-hosted transcription.


## Configuration Reference

[`.env.example`](.env.example) is the canonical list of variables. The sections below are the ones most users change.

### Model Routing

```dotenv
MODEL="nvidia_nim/meta/llama-3.1-8b-instruct"
MODEL_OPUS=
MODEL_SONNET=
MODEL_HAIKU=
ENABLE_MODEL_THINKING=true
ENABLE_OPUS_THINKING=
ENABLE_SONNET_THINKING=
ENABLE_HAIKU_THINKING=
```

Blank per-tier values inherit the fallback. Blank thinking overrides inherit `ENABLE_MODEL_THINKING`.

### Provider Keys And URLs

```dotenv
# Single key or comma-separated for round-robin rotation
NVIDIA_NIM_API_KEY=""
OPENROUTER_API_KEY=""
DEEPSEEK_API_KEY=""
OLLAMA_API_KEY=""
```

Proxy settings are per provider:

```dotenv
NVIDIA_NIM_PROXY=""
OPENROUTER_PROXY=""
OLLAMA_PROXY=""
```

### Rate Limits And Timeouts

```dotenv
PROVIDER_RATE_LIMIT=1
PROVIDER_RATE_WINDOW=3
PROVIDER_MAX_CONCURRENCY=5
HTTP_READ_TIMEOUT=300
HTTP_WRITE_TIMEOUT=10
HTTP_CONNECT_TIMEOUT=10
```

Use lower limits for free hosted providers; higher concurrency is fine when you have multiple API keys in rotation.

### Security And Diagnostics

```dotenv
ANTHROPIC_AUTH_TOKEN=
LOG_RAW_API_PAYLOADS=false
LOG_RAW_SSE_EVENTS=false
LOG_API_ERROR_TRACEBACKS=false
LOG_RAW_MESSAGING_CONTENT=false
LOG_RAW_CLI_DIAGNOSTICS=false
LOG_MESSAGING_ERROR_DETAILS=false
```

Raw logging flags can expose prompts, tool arguments, paths, and model output. Keep them off unless you are debugging locally.

### Local Web Tools

```dotenv
ENABLE_WEB_SERVER_TOOLS=true
WEB_FETCH_ALLOWED_SCHEMES=http,https
WEB_FETCH_ALLOW_PRIVATE_NETWORKS=false
```

These tools perform outbound HTTP from the proxy. Keep private-network access disabled unless you are in a controlled environment.

## How It Works

```text
Claude Code CLI / VS Code / JetBrains
        │
        │  Anthropic Messages API
        ▼
Free Claude Code Proxy (:8082)
        │
        │  round-robin key rotation
        │  provider-specific request/stream adapter
        ▼
NVIDIA NIM / OpenRouter / DeepSeek / Ollama Cloud
```

Important pieces:

- FastAPI exposes Anthropic-compatible routes: `/v1/messages`, `/v1/messages/count_tokens`, `/v1/models`.
- Model routing resolves Claude model names to `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU`, or `MODEL`.
- NIM uses OpenAI chat streaming translated into Anthropic SSE.
- OpenRouter and DeepSeek use Anthropic Messages style transports.
- **Key rotation** cycles API keys per-request across all configured keys for each provider.
- The proxy normalizes thinking blocks, tool calls, token usage metadata, and provider errors into the shape Claude Code expects.
- Request optimizations answer trivial Claude Code probes locally to save latency and quota.

## Troubleshooting

### Claude Code says `undefined ... input_tokens`, `$.speed`, or malformed response

Update to the latest commit first. Then check:

- `ANTHROPIC_BASE_URL` is `http://localhost:8082`, not `http://localhost:8082/v1`.
- The proxy is returning Server-Sent Events for `/v1/messages`.
- `server.log` contains no upstream 400/500 response before the malformed-response error.

### Provider disconnects during streaming

Errors like `incomplete chunked read`, `server disconnected`, or a peer closing the body usually come from the upstream provider or gateway. Reduce concurrency, raise timeouts, or retry later.

### Tool calls work on one model but not another

Tool support is model and provider dependent. Some OpenAI-compatible models emit malformed tool-call deltas, omit tool names, or return tool calls as plain text. Try another model or provider before assuming the proxy is broken.

### The VS Code extension still shows a login screen

Confirm the extension environment variables are set, then reload the extension or restart VS Code. The browser login flow may still appear once; the local proxy is used when `ANTHROPIC_BASE_URL` is active in the extension process.

## Development

### Project Structure

```text
free-claude-code/
├── server.py              # ASGI entry point (reads $PORT for Render)
├── Dockerfile             # Production container (Debian + uv + Python 3.14)
├── render.yaml            # Render Blueprint for one-click deploy
├── api/                   # FastAPI routes, service layer, routing, optimizations
├── core/                  # Shared Anthropic protocol helpers and SSE utilities
├── providers/             # Provider transports, registry, key rotation, rate limiting
│   └── key_rotator.py     # Thread-safe round-robin key rotation
├── messaging/             # Discord/Telegram adapters, sessions, voice
├── cli/                   # Package entry points and Claude process management
├── config/                # Settings, provider catalog, logging
└── tests/                 # Unit and contract tests (1159 tests)
```

### Commands

```bash
uv run ruff format
uv run ruff check
uv run ty check
uv run pytest
```

Run them in that order before pushing. CI enforces the same checks.

### Package Scripts

`pyproject.toml` installs:

- `free-claude-code`: starts the proxy with configured host and port.
- `fcc-init`: creates the user config template at `~/.config/free-claude-code/.env`.

### Extending

- Add OpenAI-compatible providers by extending `OpenAIChatTransport`.
- Add Anthropic Messages providers by extending `AnthropicMessagesTransport`.
- Register provider metadata in `config.provider_catalog` and factory wiring in `providers.registry`.
- Add messaging platforms by implementing the `MessagingPlatform` interface in `messaging/`.

## Contributing

- Report bugs and feature requests in [Issues](https://github.com/technicalboy2023/free-claude-code/issues).
- Keep changes small and covered by focused tests.
- Run the full check sequence before opening a pull request.

## License

MIT License. See [LICENSE](LICENSE) for details.
