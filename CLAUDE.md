# Claude Code devcontainer setup (agent guide)

This is the **AI-agent-facing** documentation for the current state of this repo.

- **Human-facing overview**: `README.md`
- **Local/self-hosted alternatives**: `LOCAL_MODEL_ALTERNATIVES.md`, `LOCAL_GPU_BOX_GUIDE.md`

## What this repo does (current state)

It provides a devcontainer + Makefile workflow to run **Claude Code CLI** against different backends.

There are two *modes*:

- **Mode A (native GCP Vertex AI)**: Claude Code talks to Vertex directly (no proxy).
- **Mode B (proxy mode via LiteLLM on `localhost:4000`)**: Claude Code talks to LiteLLM, which routes to:
  - GitHub Copilot (Claude models via Copilot subscription)
  - Ollama on the host (best-effort; not full Claude Code agent parity)

## Non-goals / known limitations (important)

- **Ollama local models are not guaranteed to support Claude Code agent/skills parity.**
  - Even if requests succeed, local models can output malformed tool/skill protocol payloads which break the Claude Code REPL experience.
  - Treat Ollama mode as “best-effort local chat/coding suggestions”, not a guaranteed replacement for Claude.

- **“Claude thinking” semantics are not preserved for local models.**
  - Claude Code can send advanced/experimental parameters (e.g. reasoning/thinking controls). Some backends reject them; others interpret them differently.
  - This repo prioritizes robustness via dropping unsupported params (see `drop_params` below).

## Key files

- **Orchestration**
  - `Makefile` (targets)
  - `scripts/manage.py` (implementation; class-based `ClaudeSetupManager`)

- **Templates / runtime state**
  - `.devcontainer/sample.env` (template, committed)
  - `.devcontainer/.env` (runtime, gitignored; may be filtered by tooling)
  - `~/.claude/settings.json` (runtime; written by `scripts/manage.py`)

### Tooling caveat: `.devcontainer/.env` may be unreadable

Some environments filter `.devcontainer/.env` from automated tooling access. When debugging, assume:
- you might not be able to “read it programmatically” from some agents/tools
- you can always inspect it directly in your terminal/editor

- **LiteLLM routing**
  - `litellm/config.copilot.yaml` (proxy mode → Copilot)
  - `litellm/config.ollama.yaml` (proxy mode → Ollama on host)
  - `litellm/config.gcp.yaml` exists but **GCP is configured as native Vertex** in this repo’s current logic (not via LiteLLM).

## Commands (user workflow)

- `make help` (lists Make targets)
- `make script-help` (shows `scripts/manage.py` CLI help)

Provider setup:
- `make setup-gcp` (native Vertex; stops LiteLLM)
- `make setup-copilot` (proxy mode; starts LiteLLM + ensures Copilot auth)
- `make setup-ollama` (proxy mode; starts LiteLLM; Ollama must run on host)

Control/status:
- `make status`
- `make start` / `make stop` (LiteLLM process only)
- `make clean` (removes `.devcontainer/.env` and `~/.claude/settings.json`)

## Provider behaviors (important implementation details)

### GCP (native Vertex)

`make setup-gcp`:
- Ensures `GCP_PROJECT_ID` exists (auto-detects from `gcloud config get-value project` or prompts)
- Runs `gcloud auth application-default login` (ADC)
- Writes `~/.claude/settings.json` containing **Vertex-native vars** only:
  - `CLAUDE_CODE_USE_VERTEX=1`
  - `ANTHROPIC_VERTEX_PROJECT_ID`
  - `CLOUD_ML_REGION`
  - optional `ANTHROPIC_MODEL` and `ANTHROPIC_SMALL_FAST_MODEL` (Vertex Claude model IDs)
- Ensures LiteLLM is stopped to avoid hybrid configs

### Proxy mode (Copilot / Ollama)

`make setup-copilot` / `make setup-ollama`:
- Writes `~/.claude/settings.json` with:
  - `ANTHROPIC_BASE_URL=http://localhost:<LITELLM_PORT>` (default 4000)
  - `ANTHROPIC_AUTH_TOKEN=<LITELLM_MASTER_KEY>`
  - model aliases: `opus`, `sonnet`, `haiku`
- Starts LiteLLM as a background process (`/tmp/litellm.pid`, `/tmp/litellm.log`)

#### Copilot auth (device flow)

LiteLLM’s `github_copilot/*` provider uses GitHub device login on first use.

This repo’s `scripts/manage.py` now:
- surfaces the device-login prompt from `/tmp/litellm.log` when needed
- actively waits for Copilot to respond before completing `make setup-copilot`

Token files are stored under:
- `~/.config/litellm/github_copilot/api-key.json`
- `~/.config/litellm/github_copilot/access-token`

Common failure mode:
- LiteLLM prints the GitHub device-login URL/code into `/tmp/litellm.log` (because the proxy is started in the background), so users miss it and authentication times out.
- `scripts/manage.py` contains logic to surface that prompt and to wait for Copilot to respond before returning success.

#### “drop_params” is enabled for robustness

We observed real failures from provider-unsupported params sent by Claude Code / gateway paths (e.g. `reasoning_effort`).
Therefore:

- `litellm/config.copilot.yaml` has:
  - `litellm_settings.drop_params: true`
- `litellm/config.ollama.yaml` has:
  - `litellm_settings.drop_params: true`

Effect: LiteLLM drops unsupported params instead of returning 400.

Implications:
- **Pro:** avoids hard failures when Claude Code (or gateway adapters) send provider-unsupported params (e.g. `reasoning_effort`).
- **Con:** silently disables “advanced” features that depend on those params for that provider. Tool calling generally still works, but provider-specific extras may be ignored.

## Ollama limitations (do not overpromise)

Ollama via LiteLLM can be useful for “local chat/coding suggestions”, but may **not** reliably support Claude Code’s full agent/skills/tooling contract.

Observed failure mode:
- Claude Code receives malformed “Skill/tool” shaped output from local models, causing confusing REPL behavior.

If full agent/skills reliability is required for local/self-hosted, see:
- `LOCAL_MODEL_ALTERNATIVES.md` (includes vLLM and `ccr-local`)
- `LOCAL_GPU_BOX_GUIDE.md` (hardware guidance)

## Container networking (Ollama)

Ollama is expected to run on the **host**, not inside the container.

The devcontainer enables host reachability via:
- `--add-host=host.docker.internal:host-gateway` (Linux)

Ollama endpoint from within container:
- `http://host.docker.internal:11434`

## Common troubleshooting (high-signal)

- **Proxy running but `/health` is 401**
  - Expected when LiteLLM auth is enabled.
  - Use `Authorization: Bearer <LITELLM_MASTER_KEY>` for `/health`.

- **Copilot setup times out**
  - Check `/tmp/litellm.log` for: `Please visit https://github.com/login/device and enter code ...`
  - Complete device login, then rerun `make setup-copilot`.

- **LiteLLM prints a site-packages UI permission error**
  - LiteLLM may try to restructure its packaged admin UI under site-packages in devcontainers.
  - `scripts/manage.py` sets `DISABLE_ADMIN_UI=True` in the LiteLLM process environment to avoid this.

## Repo hygiene notes (for agents)

- Do not commit runtime artifacts:
  - `.devcontainer/.env` (gitignored)
  - `~/.claude/settings.json` (user runtime)
  - `/tmp/litellm.pid`, `/tmp/litellm.log`
  - `scripts/__pycache__/` (Python cache; ignore/remove if it shows up)

