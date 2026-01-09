# Claude Code Multi-Provider Setup - Technical Documentation for AI Agents

## Repository Purpose

This repository provides a devcontainer-based setup for Claude Code with support for three LLM providers via LiteLLM proxy.

## Critical Understanding for AI Agents

**Setup is NOT automatic.** When the devcontainer starts:
1. A welcome message is displayed via `postCreateCommand`
2. NO services are started automatically
3. User must manually run `make setup-<provider>` to configure
4. This is intentional - gives developers explicit control over provider selection

**File Categories:**
- **READ-ONLY Templates**: `sample.env`, `litellm/config.*.yaml` (committed to git)
- **GENERATED at Runtime**: `.env`, `~/.claude/settings.json` (gitignored, created by Makefile)

## Architecture

```
Claude Code → LiteLLM Proxy (localhost:4000) → [GCP Vertex AI | Ollama | GitHub Copilot]
```

**Key Components:**
- **LiteLLM Proxy**: Unified gateway routing requests to different providers
- **Makefile**: Interactive setup commands for provider selection
- **devcontainer**: Pre-configured environment with all dependencies

## File Structure

```
.devcontainer/
├── Dockerfile                     # Container image with gcloud, LiteLLM, Claude Code
├── devcontainer.json             # VS Code devcontainer configuration
├── sample.env                    # Comprehensive environment variable template (all providers)
└── .env                          # Active config (created by make setup-*)

litellm/
├── config.gcp.yaml               # LiteLLM config for GCP Vertex AI
├── config.ollama.yaml            # LiteLLM config for Ollama
└── config.copilot.yaml           # LiteLLM config for GitHub Copilot

Makefile                           # Setup orchestration
~/.claude/settings.json           # Claude Code configuration (created by setup)
```

## Configuration Details

### LiteLLM Configs

Each YAML file defines three model aliases:

**litellm/config.gcp.yaml:**
```yaml
model_list:
  - model_name: opus
    litellm_params:
      model: vertex_ai/claude-opus-4-5@20251101
      vertex_project: ${GCP_PROJECT_ID}
      vertex_location: us-central1
  - model_name: sonnet
    litellm_params:
      model: vertex_ai/claude-sonnet-4-5@20250929
      vertex_project: ${GCP_PROJECT_ID}
      vertex_location: us-central1
  - model_name: haiku
    litellm_params:
      model: vertex_ai/claude-haiku-4-5@20250925
      vertex_project: ${GCP_PROJECT_ID}
      vertex_location: us-central1
```

**litellm/config.ollama.yaml:**
```yaml
model_list:
  - model_name: opus
    litellm_params:
      model: ollama_chat/llama3.1:70b
      api_base: http://host.docker.internal:11434  # Connects to host
  - model_name: sonnet
    litellm_params:
      model: ollama_chat/llama3.1:8b
      api_base: http://host.docker.internal:11434  # Connects to host
  - model_name: haiku
    litellm_params:
      model: ollama_chat/qwen2.5:3b
      api_base: http://host.docker.internal:11434  # Connects to host
```

**Critical:** Ollama runs on the HOST machine, not in the container. The `host.docker.internal` hostname allows the container to reach the host.

**litellm/config.copilot.yaml:**
```yaml
model_list:
  - model_name: opus
    litellm_params:
      model: github_copilot/claude-opus-4.5
      extra_headers:
        Editor-Version: "vscode/1.107.0"
        Copilot-Integration-Id: "vscode-chat"
  - model_name: sonnet
    litellm_params:
      model: github_copilot/claude-sonnet-4.5
      extra_headers:
        Editor-Version: "vscode/1.107.0"
        Copilot-Integration-Id: "vscode-chat"
  - model_name: haiku
    litellm_params:
      model: github_copilot/claude-haiku-4.5
      extra_headers:
        Editor-Version: "vscode/1.107.0"
        Copilot-Integration-Id: "vscode-chat"
```

### Claude Code Configuration

Located at `~/.claude/settings.json` (created by `make setup-*`):

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:4000",
    "ANTHROPIC_AUTH_TOKEN": "<LITELLM_MASTER_KEY>",
    "ANTHROPIC_MODEL": "sonnet",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku",
    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "true"
  }
}
```

**Model Usage:**
- `ANTHROPIC_DEFAULT_OPUS_MODEL`: Complex reasoning, planning mode
- `ANTHROPIC_DEFAULT_SONNET_MODEL`: General coding, execution mode
- `ANTHROPIC_DEFAULT_HAIKU_MODEL`: Fast operations (grep, glob, quick tasks)
- `CLAUDE_CODE_SUBAGENT_MODEL`: Subagent operations

## Makefile Internal Flow

### How Setup Actually Works

Each `make setup-<provider>` command executes a chain of internal targets. Understanding this flow is critical:

**Example: `make setup-gcp` execution flow:**

```
make setup-gcp
  └─> _check_gcloud           # Verify gcloud CLI installed
  └─> _setup_env PROFILE=gcp  # Handle .env file
       │
       ├─> If .env doesn't exist:
       │    1. Copy sample.env → .env
       │    2. Update LITELLM_CONFIG=config.gcp.yaml
       │    3. Update PROFILE=gcp
       │    4. Prompt user to edit GCP_PROJECT_ID and LITELLM_MASTER_KEY
       │    5. Wait for user to press Enter
       │
       └─> If .env exists:
            1. Update LITELLM_CONFIG=config.gcp.yaml
            2. Update PROFILE=gcp
            3. Existing values (GCP_PROJECT_ID, LITELLM_MASTER_KEY) preserved

  └─> _authenticate_gcp       # GCP-specific authentication
       │
       ├─> Source .env to get $GCP_PROJECT_ID
       ├─> Run: gcloud config set project $GCP_PROJECT_ID
       └─> Run: gcloud auth application-default login (opens browser)

  └─> _setup_claude_config    # Generate Claude Code settings
       │
       ├─> Create ~/.claude/ directory
       ├─> Source .env to get $LITELLM_PORT and $LITELLM_MASTER_KEY
       └─> Generate ~/.claude/settings.json with printf
            (Uses model aliases: opus, sonnet, haiku)

  └─> _start_litellm          # Start LiteLLM proxy
       │
       ├─> Stop any existing LiteLLM process
       ├─> Source .env to get config values
       ├─> Start: litellm --config litellm/$LITELLM_CONFIG
       ├─> Save PID to /tmp/litellm.pid
       ├─> Health check loop (5 attempts, 1s each):
       │    └─> curl http://localhost:$LITELLM_PORT/health
       └─> Report success or failure
```

**Critical Implementation Details:**

1. **Environment Variable Flow:**
   - `.env` contains: `LITELLM_CONFIG=config.gcp.yaml` and `GCP_PROJECT_ID=my-project`
   - LiteLLM reads `litellm/config.gcp.yaml` which has `vertex_project: ${GCP_PROJECT_ID}`
   - LiteLLM substitutes `${GCP_PROJECT_ID}` from environment when it starts
   - This is why `.env` must be sourced before starting LiteLLM

2. **The .env File Lifecycle:**
   ```
   First run:  sample.env → .env (with profile updates) → user edits → sourced by Makefile
   Switch:     existing .env (profile values updated) → sourced by Makefile
   ```

3. **Why sample.env Stays Unchanged:**
   - `sample.env` is git-tracked comprehensive template with ALL variables
   - `.env` is gitignored (contains sensitive data like GCP_PROJECT_ID)
   - Never edit `sample.env`; always edit the generated `.env` file
   - `sample.env` serves as reference documentation for all possible variables

### Setup Commands

**make setup-gcp:**
Executes: `_check_gcloud` → `_setup_env` → `_authenticate_gcp` → `_setup_claude_config` → `_start_litellm`

**make setup-ollama:**
Executes: `_check_ollama` → `_setup_env` → `_setup_claude_config` → `_start_litellm`

**make setup-copilot:**
Executes: `_check_copilot` → `_setup_env` → `_setup_claude_config` → `_start_litellm`

### Utility Commands

**make status:**
- Shows active profile from `.env`
- Checks if LiteLLM process is running (via PID file)
- Verifies Claude config exists

**make stop:**
- Kills LiteLLM proxy process
- Removes PID file

**make clean:**
- Stops LiteLLM
- Removes `.env` and `~/.claude/settings.json`

## Process Management

- LiteLLM runs as background process via `nohup`
- PID stored in `/tmp/litellm.pid`
- Logs written to `/tmp/litellm.log`
- Port: 4000 (configurable via `LITELLM_PORT` in `.env`)

## Container Networking for Ollama

**Critical Understanding:**

Ollama runs on the **HOST machine**, not inside the devcontainer. This is because:
1. Ollama models are large (GBs) and shouldn't be in container images
2. Model downloads are slow and should be reused across container rebuilds
3. Ollama service is resource-intensive (better on host)

**Network Configuration:**

```
┌─────────────────────┐
│ HOST MACHINE        │
│                     │
│ Ollama :11434       │ ← Running on host
└─────────────────────┘
          ▲
          │ host.docker.internal:11434
          │
┌─────────────────────┐
│ DEVCONTAINER        │
│                     │
│ LiteLLM :4000       │ ← Connects to host
│ Claude Code         │
└─────────────────────┘
```

**How host.docker.internal Works:**

- `localhost` inside a container = the container itself
- `host.docker.internal` = special DNS name that resolves to the host machine
- Docker Desktop provides this automatically on Mac/Windows
- Linux needs `--add-host=host.docker.internal:host-gateway` (configured in devcontainer.json)

**Configuration in devcontainer.json:**
```json
"runArgs": [
  "--add-host=host.docker.internal:host-gateway"
]
```

This ensures `host.docker.internal` works on all platforms (Mac, Windows, Linux).

## Authentication Methods

**GCP Vertex AI:**
- Uses Application Default Credentials (ADC)
- Set via `gcloud auth application-default login`
- Credentials stored in `~/.config/gcloud/application_default_credentials.json`
- Environment variable: `GOOGLE_APPLICATION_CREDENTIALS`

**Ollama:**
- No authentication required
- Direct API access to `http://host.docker.internal:11434`
- **Must be running on host machine** before `make setup-ollama`

**GitHub Copilot:**
- Authenticated via VS Code extension
- LiteLLM uses Copilot session from VS Code

## Environment Variables

**.env (active configuration):**
```bash
# GCP Example
LITELLM_CONFIG=config.gcp.yaml
GCP_PROJECT_ID=your-project-id
CLOUD_ML_REGION=us-central1
LITELLM_MASTER_KEY=sk-1234-change-me
LITELLM_PORT=4000
PROFILE=gcp

# Ollama Example
LITELLM_CONFIG=config.ollama.yaml
LITELLM_MASTER_KEY=sk-1234-change-me
LITELLM_PORT=4000
PROFILE=ollama

# Copilot Example
LITELLM_CONFIG=config.copilot.yaml
LITELLM_MASTER_KEY=sk-1234-change-me
LITELLM_PORT=4000
PROFILE=copilot
```

## Dependencies

**Dockerfile installs:**
- `google-cloud-sdk` - GCP authentication and API access
- `litellm[proxy]` - LLM gateway
- `claude-code` - Claude Code CLI
- `uv` - Python package manager for MCP servers
- `npm@11.4.2` - Node package manager for MCP servers

**Base Image:**
- `mcr.microsoft.com/devcontainers/javascript-node:20-bookworm`

**External Dependencies (not in container):**
- **Ollama** - Must be installed and running on HOST machine for Ollama provider

## Port Forwarding & Networking

**Container Ports (forwarded to host):**
- `3000` - Next.js application (example)
- `4000` - LiteLLM proxy

**Host Ports (accessed from container):**
- `11434` - Ollama on host (via `host.docker.internal:11434`)
  - NOT in `forwardPorts` because it's a host service, not a container service
  - Accessed via `--add-host=host.docker.internal:host-gateway` in runArgs

## Model Selection Strategy

LiteLLM provides unified model aliases that map to provider-specific models:

| Alias | GCP Vertex AI | Ollama | Copilot | Purpose |
|-------|---------------|--------|---------|---------|
| opus | claude-opus-4-5@20251101 | llama3.1:70b | claude-opus-4.5 | Complex reasoning |
| sonnet | claude-sonnet-4-5@20250929 | llama3.1:8b | claude-sonnet-4.5 | Daily tasks |
| haiku | claude-haiku-4-5@20250925 | qwen2.5:3b | claude-haiku-4.5 | Fast operations |

## Container Lifecycle & State Management

### What Happens on Container Start/Rebuild

**Container Build (first time or after rebuild):**
1. Dockerfile installs: gcloud, LiteLLM, Claude Code, uv, npm
2. devcontainer.json forwards ports 3000, 4000
3. `postCreateCommand` runs:
   - Adds git safe directory
   - Displays welcome message with setup instructions
4. **NO automatic setup occurs** - container waits for user action

**Container Start (after stop/restart):**
1. Container restarts with all tools installed
2. `.env` file persists (if it exists from previous setup)
3. `~/.claude/settings.json` persists
4. **LiteLLM proxy does NOT auto-start** - must run `make setup-<provider>` again
5. PID file (`/tmp/litellm.pid`) is stale and cleaned on next `make stop`

**Key Insight:**
- Setup is **session-based**, not persistent across container restarts
- After container restart, simply run `make setup-<provider>` again (uses existing `.env`)
- If `.env` already exists, setup updates only LITELLM_CONFIG and PROFILE (preserves other values)

### System State Diagram

```
[Container Start]
       │
       ▼
[No .env, No LiteLLM, No ~/.claude/settings.json]
       │
       │ make setup-gcp
       ▼
[Has .env, LiteLLM running, Has ~/.claude/settings.json]
       │
       │ Container restart
       ▼
[Has .env, NO LiteLLM, Has ~/.claude/settings.json]
       │
       │ make setup-gcp (reuses existing .env)
       ▼
[Has .env, LiteLLM running, Has ~/.claude/settings.json]
```

## Switching Providers

**Complete switch workflow:**
```bash
make stop                # Stop LiteLLM proxy
make setup-<provider>    # Setup new provider (overwrites .env)
make status              # Verify new configuration
```

**What actually happens during switch:**
1. `make stop` kills LiteLLM process, removes PID file
2. `make setup-<provider>` updates `.env` (changes LITELLM_CONFIG and PROFILE only)
3. Existing values (GCP_PROJECT_ID, LITELLM_MASTER_KEY) are preserved
4. New LiteLLM config is loaded, pointing to different provider
5. `~/.claude/settings.json` stays the same (uses model aliases)

**No container rebuild required** - all changes are runtime configuration.

## Security Notes

- `.env` is gitignored (contains sensitive data)
- LiteLLM proxy only listens on localhost:4000
- GCP uses ADC (no hardcoded credentials)
- Master key is local-only (not exposed externally)

## Troubleshooting Decision Tree

### Scenario 1: "Claude Code says it can't connect to API"

**Diagnostic steps:**
```bash
# Step 1: Is LiteLLM running?
make status
# OR
ps aux | grep litellm
curl http://localhost:4000/health

# If NO → Start LiteLLM
make setup-<provider>

# If YES → Check Claude settings
cat ~/.claude/settings.json
# Verify: ANTHROPIC_BASE_URL="http://localhost:4000"
# Verify: ANTHROPIC_AUTH_TOKEN matches LITELLM_MASTER_KEY in .env
```

### Scenario 2: "make setup-gcp fails during authentication"

**Diagnostic steps:**
```bash
# Step 1: Is gcloud installed?
which gcloud
# If NO → Error in Dockerfile build

# Step 2: Can gcloud reach GCP?
gcloud auth application-default login
# If fails → Network/firewall issue

# Step 3: Is project ID valid?
cat .devcontainer/.env | grep GCP_PROJECT_ID
gcloud projects describe <PROJECT_ID>
# If fails → Invalid project or no access
```

### Scenario 3: "LiteLLM starts but requests fail"

**Diagnostic steps:**
```bash
# Step 1: Check LiteLLM logs for errors
tail -f /tmp/litellm.log
# Look for: authentication errors, model not found, API errors

# Step 2: Verify environment variables
cat .devcontainer/.env
# Ensure GCP_PROJECT_ID is set (for GCP)
# Ensure LITELLM_CONFIG points to correct yaml

# Step 3: Test provider directly
# For GCP:
gcloud auth application-default print-access-token
# Should return a token

# For Ollama:
curl http://host.docker.internal:11434/api/tags
# Should return list of models (Ollama must be running on HOST)

# For Copilot:
# Check VS Code status bar for Copilot status
```

### Scenario 4: "Container rebuilt, now nothing works"

**What happened:**
- Container rebuild clears `/tmp/` (PID file lost)
- LiteLLM process is not running
- `.env` and `~/.claude/settings.json` persist, but need to re-run setup

**Fix:**
```bash
make setup-<provider>  # Reuses existing .env
```

### Scenario 5: "Switching from GCP to Ollama, getting errors"

**Common issue:**
- Rare, but if switching profiles, ensure LITELLM_CONFIG matches PROFILE

**Fix:**
```bash
make stop
make setup-ollama     # Updates LITELLM_CONFIG=config.ollama.yaml and PROFILE=ollama
# GCP_PROJECT_ID remains in .env but is ignored by Ollama config
```

### Scenario 6: "make status shows LiteLLM running but Claude Code fails"

**Diagnostic:**
```bash
# Test LiteLLM endpoint directly
curl -X POST http://localhost:4000/chat/completions \
  -H "Authorization: Bearer $(grep LITELLM_MASTER_KEY .devcontainer/.env | cut -d'=' -f2)" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sonnet",
    "messages": [{"role": "user", "content": "test"}]
  }'

# If this fails → LiteLLM config issue
# If this works → Claude Code config issue
```

### Common Error Messages

**"Error: sample.env not found"**
- Cause: `.devcontainer/sample.env` file missing
- Fix: Ensure `sample.env` exists in `.devcontainer/` folder
- Valid profiles: `gcp`, `ollama`, `copilot`

**"Failed to start LiteLLM. Check /tmp/litellm.log"**
- Cause: LiteLLM config syntax error or missing environment variable
- Fix:
  ```bash
  tail -f /tmp/litellm.log  # Read actual error
  cat .devcontainer/.env     # Verify all variables set
  ```

**"Ollama not running on host"**
- Cause: Ollama service not started on HOST machine
- Fix: Run `ollama serve` on your HOST machine (outside devcontainer)
- Verify: `curl http://host.docker.internal:11434/api/tags` from inside devcontainer

**"gcloud: command not found"**
- Cause: Dockerfile didn't install gcloud (unlikely) or wrong shell path
- Fix: Rebuild container

**"Authentication errors" in LiteLLM logs (GCP)**
- Cause: ADC credentials not set or expired
- Fix: `gcloud auth application-default login`

## Detailed Troubleshooting

**LiteLLM not starting:**
```bash
# Check logs first
tail -f /tmp/litellm.log

# Verify config syntax
cat .devcontainer/.env
cat litellm/$(grep LITELLM_CONFIG .devcontainer/.env | cut -d'=' -f2)

# Check process
ps aux | grep litellm

# Manual start for debugging
. .devcontainer/.env
litellm --config litellm/$LITELLM_CONFIG --port $LITELLM_PORT
```

**GCP authentication issues:**
```bash
# Re-authenticate
gcloud auth application-default login

# Verify project
gcloud config get-value project

# Check credentials file
cat ~/.config/gcloud/application_default_credentials.json

# Test Vertex AI access
gcloud ai models list --region=us-central1
```

**Ollama connection failed:**
```bash
# IMPORTANT: Ollama must run on HOST, not in container

# From INSIDE devcontainer, test connection to host:
curl http://host.docker.internal:11434/api/tags
# If fails → Ollama not running on host OR networking issue

# From HOST machine (outside devcontainer), check if Ollama is running:
curl http://localhost:11434/api/tags
# If fails → Start Ollama on host

# Start Ollama on HOST machine:
ollama serve

# Verify models installed (on HOST):
ollama list

# Pull missing models (on HOST):
ollama pull llama3.1:70b
ollama pull llama3.1:8b
ollama pull qwen2.5:3b

# Test from container again:
curl http://host.docker.internal:11434/api/tags
```

**Claude Code not finding models:**
```bash
# Verify proxy is healthy
curl http://localhost:4000/health

# Check Claude settings
cat ~/.claude/settings.json

# Verify model aliases exist in LiteLLM config
cat litellm/$(grep LITELLM_CONFIG .devcontainer/.env | cut -d'=' -f2)

# Check LiteLLM logs for model loading
tail -f /tmp/litellm.log
```

## Integration with Existing Projects

To add this setup to another project:

1. Copy `.devcontainer/` directory
2. Copy `Makefile`
3. Add to `.gitignore`:
   ```
   .devcontainer/.env
   ```
4. Rebuild devcontainer
5. Run `make setup-<provider>`

## Quick Reference Cheat Sheet

### Essential Commands
```bash
# Setup
make setup-gcp         # Configure for GCP Vertex AI
make setup-ollama      # Configure for Ollama
make setup-copilot     # Configure for GitHub Copilot

# Status & Control
make status            # Show current configuration and service status
make stop              # Stop LiteLLM proxy
make clean             # Stop services and remove all configuration
make help              # Show all available commands

# Troubleshooting
tail -f /tmp/litellm.log                    # View LiteLLM logs
cat .devcontainer/.env                       # Check active configuration
cat ~/.claude/settings.json                  # Check Claude Code settings
curl http://localhost:4000/health            # Test LiteLLM proxy
ps aux | grep litellm                        # Check if LiteLLM is running
```

### File Reference Guide

| File | Purpose | Edit? | Committed to Git? |
|------|---------|-------|-------------------|
| `litellm/config.gcp.yaml` | GCP model routing | ✅ (to change models) | ✅ Yes |
| `litellm/config.ollama.yaml` | Ollama model routing | ✅ (to change models) | ✅ Yes |
| `litellm/config.copilot.yaml` | Copilot model routing | ✅ (to change models) | ✅ Yes |
| `.devcontainer/sample.env` | Comprehensive env template (all providers) | ❌ Never | ✅ Yes |
| `.devcontainer/.env` | Active configuration | ✅ (after creation) | ❌ No (gitignored) |
| `~/.claude/settings.json` | Claude Code settings | ❌ (auto-generated) | ❌ No |
| `/tmp/litellm.pid` | LiteLLM process ID | ❌ Never | ❌ No |
| `/tmp/litellm.log` | LiteLLM logs | ❌ Never | ❌ No |
| `Makefile` | Setup orchestration | ✅ (to modify setup) | ✅ Yes |

### Decision Matrix: Which Provider to Use?

| Scenario | Recommended Provider | Why |
|----------|---------------------|-----|
| Corporate environment with GCP | **GCP Vertex AI** | Compliance, centralized billing, IAM |
| Offline development | **Ollama** | No internet required, no API costs |
| Have Copilot subscription | **GitHub Copilot** | Leverage existing subscription |
| Testing/development | **Ollama** | Fast, local, no rate limits |
| Production corporate use | **GCP Vertex AI** | Audit logs, governance, SLAs |
| Cost-sensitive project | **Ollama** | Free after model download |

### Environment Variable Quick Reference

**Required in .env for each provider:**

**GCP:**
- `LITELLM_CONFIG=config.gcp.yaml`
- `GCP_PROJECT_ID=<your-project>`
- `CLOUD_ML_REGION=us-central1`
- `LITELLM_MASTER_KEY=<random-key>`
- `LITELLM_PORT=4000`
- `PROFILE=gcp`

**Ollama:**
- `LITELLM_CONFIG=config.ollama.yaml`
- `LITELLM_MASTER_KEY=<random-key>`
- `LITELLM_PORT=4000`
- `PROFILE=ollama`

**Copilot:**
- `LITELLM_CONFIG=config.copilot.yaml`
- `LITELLM_MASTER_KEY=<random-key>`
- `LITELLM_PORT=4000`
- `PROFILE=copilot`

### Common Tasks & Solutions

**Task: First time setup**
```bash
# 1. Open in devcontainer
# 2. Choose provider and run:
make setup-gcp  # or setup-ollama or setup-copilot
# 3. Edit .env with actual values when prompted
# 4. Verify:
make status
```

**Task: Container restarted**
```bash
# Simply re-run setup (reuses existing .env):
make setup-<provider>
```

**Task: Switch from GCP to Ollama**
```bash
make stop
make setup-ollama
make status
```

**Task: Check if everything is working**
```bash
# 1. Check LiteLLM is running:
curl http://localhost:4000/health

# 2. Check Claude Code can reach it:
cat ~/.claude/settings.json | grep ANTHROPIC_BASE_URL

# 3. Test with Claude Code:
claude /status
```

**Task: Debug LiteLLM startup failure**
```bash
# 1. Check logs:
tail -f /tmp/litellm.log

# 2. Try manual start:
. .devcontainer/.env
litellm --config litellm/$LITELLM_CONFIG --port $LITELLM_PORT

# 3. Look for: YAML syntax errors, missing env vars, port conflicts
```

## References

- LiteLLM Vertex AI Provider: https://docs.litellm.ai/docs/providers/vertex
- LiteLLM Ollama Provider: https://docs.litellm.ai/docs/providers/ollama
- Claude Code Model Config: https://code.claude.com/docs/en/model-config
- Claude Code Third-Party Integrations: https://code.claude.com/docs/en/third-party-integrations
