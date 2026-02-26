# AGENTS.md

Devcontainer repo for running Claude Code CLI against GCP Vertex AI or GitHub Copilot (via LiteLLM proxy).

## Repo layout

```
Makefile                  # user-facing targets (delegates to scripts/manage.py)
scripts/manage.py         # all orchestration logic
.devcontainer/
  devcontainer.json       # container config
  Dockerfile              # image build (node:20-bookworm + gcloud + claude-code + uv)
  sample.env              # template — copy to .env and fill in
  .env                    # runtime config (gitignored)
litellm/
  config.copilot.yaml     # LiteLLM proxy routing for Copilot mode
```

## Commands

```sh
make help             # list all targets
make setup-gcp        # configure for GCP Vertex AI (stops LiteLLM)
make setup-copilot    # configure for GitHub Copilot via LiteLLM proxy
make status           # show current profile + service health
make start-litellm    # start LiteLLM proxy
make stop-litellm     # stop LiteLLM proxy
make clean            # remove .env + settings, stop services
```

## Two modes

- **GCP**: sets `CLAUDE_CODE_USE_VERTEX=1` + Vertex model IDs in `~/.claude/settings.json`. No proxy.
- **Copilot**: starts LiteLLM on `localhost:4000`, sets `ANTHROPIC_BASE_URL` to proxy. Uses GitHub device-flow auth (watch `/tmp/litellm.log` for the login URL).

## Do not commit

`.devcontainer/.env`, `~/.claude/settings.json`, `/tmp/litellm.*`, `__pycache__/`
