# Claude Code devcontainer setup (agent guide)

This is the **AI-agent-facing** documentation for the current state of this repo.

- **Human-facing overview**: `README.md`

## What this repo does (current state)

It provides a devcontainer + Makefile workflow to run **Claude Code CLI** against different backends.

There are two *modes*:

- **Mode A (native GCP Vertex AI)**: Claude Code talks to Vertex directly (no proxy).
- **Mode B (proxy mode via LiteLLM on `localhost:4000`)**: Claude Code talks to LiteLLM, which routes to GitHub Copilot (Claude models via Copilot subscription).

## Non-goals / known limitations (important)

- **"Claude thinking" semantics are not preserved for non-Anthropic backends.**
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

## Commands (user workflow)

- `make help` (lists Make targets)
- `make script-help` (shows `scripts/manage.py` CLI help)

Provider setup:
- `make setup-gcp` (native Vertex; stops LiteLLM)
- `make setup-copilot` (proxy mode; starts LiteLLM + ensures Copilot auth)

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
  - optional `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, and `ANTHROPIC_DEFAULT_HAIKU_MODEL` (Vertex Claude model IDs)
- Ensures LiteLLM is stopped to avoid hybrid configs

### Proxy mode (Copilot)

`make setup-copilot`:
- Writes `~/.claude/settings.json` with:
  - `ANTHROPIC_BASE_URL=http://localhost:<LITELLM_PORT>` (default 4000)
  - `ANTHROPIC_AUTH_TOKEN=<LITELLM_MASTER_KEY>`
  - `ANTHROPIC_DEFAULT_OPUS_MODEL=opus`
  - `ANTHROPIC_DEFAULT_SONNET_MODEL=sonnet`
  - `ANTHROPIC_DEFAULT_HAIKU_MODEL=haiku`
  - `CLAUDE_CODE_SUBAGENT_MODEL=sonnet`
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

Effect: LiteLLM drops unsupported params instead of returning 400.

Implications:
- **Pro:** avoids hard failures when Claude Code (or gateway adapters) send provider-unsupported params (e.g. `reasoning_effort`).
- **Con:** silently disables “advanced” features that depend on those params for that provider. Tool calling generally still works, but provider-specific extras may be ignored.


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

