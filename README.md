# Corporate Claude-Code Setup

## Pain Points To Solve
- Typically, developers in corporate environments cannot just use their private Claude Code subscriptions, but would like to make use of the power of Claude Code.
- If developers work on multiple projects, it can be preferable to have Claude Code installed in a project specific environment. Some project might allow the use AI assisted coding and others don't, or AI can be only used with local models.
- Often companies don't have a direct contract with Anthropic for Claude Code but have existing cloud infrastructure.

## Solution
- This repository shows a setup of Claude Code within a devcontainer. This ensures to keep the installation project local.
- The setup supports **three different LLM providers** via LiteLLM proxy:
  - **GCP Vertex AI**: Claude models consumed from Vertex AI inside a GCP Project (compliant for corporate GCP cloud landing zones)
  - **Local Ollama**: Self-hosted open-source models for offline work, highly confidential code bases, or cost-sensitive scenarios
  - **GitHub Copilot**: Claude models via existing GitHub Copilot subscription
- You can interactively choose which provider to use via simple `make` commands.

## Prerequisites

1. This repository was written with Cursor, which is able to run devcontainers. If you use another IDE, this IDE must have the capabilities to run devcontainers.
2. Choose one or more of the following providers:
   - **For GCP Vertex AI**: Access to a project in Google Cloud with Vertex AI enabled
   - **For Ollama**: Ollama installed and running locally
   - **For GitHub Copilot**: Active GitHub Copilot subscription

## Devcontainer Setup

### Dockerfile

- The devcontainer setup is configured in the folder `.devcontainer`.
- As base image a devcontainer `node` image is used to have `npm` available for running MCP servers with `npx` later on.
- `gcloud` is installed to be able to login to Google Cloud (for GCP Vertex AI provider).
- `LiteLLM` is installed to provide a unified proxy for routing requests to different LLM providers.
- `uv` is installed to have `uvx` available to run MCP servers later on.

### devcontainer.json

- Inside the `devcontainer.json` the configuration of the devcontainer is done.
- Important is the mount of the local `~/.ssh` folder to be able to push to the remote repository within the devcontainer with the same ssh setup from the local PC.
- To easily distinguish if the project is opened locally or inside the devcontainer, a custom coloring of the top-bar, side-bar, and bottom is added inside the `devcontainer.json`. This custom coloring is active when the project is opened inside the devcontainer.
- Port 4000 is forwarded for the LiteLLM proxy.

### LiteLLM Configuration Files

- Three LiteLLM configuration files define routing to different providers (located in `litellm/`):
  - `config.gcp.yaml` - Routes to GCP Vertex AI
  - `config.ollama.yaml` - Routes to local Ollama
  - `config.copilot.yaml` - Routes to GitHub Copilot
- Each config defines three model aliases (opus, sonnet, haiku) for different use cases.

## Google Cloud Setup

### GCP Project & Permissions
- You need to have access to a GCP Project.
- Inside that project you need to have the permission `Vertex AI User`.

### Vertex AI Configuration
- Inside Vertex AI go to Model Garden
- Enable an endpoint for the latest Claude Sonnet model.
  - At the time of creating this Readme, the latest version was `claude-sonnet-4-5@20250929`.
  - The model id of your activated Claude Sonnet model needs to be entered later in the `.env` file.
  - The Claude Sonnet model is later specified in the `.env` file as the `ANTHROPIC_MODEL`.
- Similarly enable an endpoint for the latest Claude Haiku model.
  - This model is later specified in the `.env` file as the `ANTHROPIC_SMALL_FAST_MODEL`.
  - At the time of creating this Readme, the latest version was `claude-haiku-4-5@20251001`.

## How To Use This Repository

### Cloning
1. Clone the repository to your machine

### Build Devcontainer
2. Go to the command palette of Cursor or Vscode with `Shift + Command + P` or `F1` and run `Reopen Devcontainer`.
3. Once this command is done, the image is built and the devcontainer is started.

### Choose Your Provider
4. After the devcontainer starts, choose which LLM provider you want to use:

#### Option A: GCP Vertex AI
```bash
make setup-gcp
```
- You will be prompted to edit `.devcontainer/.env` with your GCP project ID
- The setup will authenticate you to Google Cloud via browser
- Click on the authentication link with `Command + click` and follow the instructions

#### Option B: Local Ollama
```bash
# IMPORTANT: Ollama must run on your HOST machine, not inside the container
# Open a terminal on your host (outside the devcontainer) and run:

# 1. Start Ollama service on host
ollama serve

# 2. Pull required models (on host)
ollama pull llama3.1:70b
ollama pull llama3.1:8b
ollama pull qwen2.5:3b

# 3. Then, inside the devcontainer, setup Claude Code
make setup-ollama
```

**Note:** The devcontainer connects to Ollama running on your host machine via `host.docker.internal:11434`. This works on Windows, macOS, and Linux (configured via devcontainer.json).

#### Option C: GitHub Copilot
```bash
# Ensure you're logged in to GitHub Copilot in VS Code/Cursor first
make setup-copilot
```

### Verify Setup
5. Check that everything is configured correctly:
```bash
make status
```

### Run Claude Code
6. Now you should be able to open a terminal in `vscode` or `cursor` and type in `claude`. Et voilá, Claude Code is starting, ready to be your helpful coding assistant.

### Switch Providers (Optional)
7. You can switch between providers at any time:
```bash
make stop              # Stop current provider
make setup-<provider>  # Start new provider (gcp, ollama, or copilot)
```

## Available Commands

All setup is managed via the `Makefile`:

```bash
make help           # Show all available commands
make setup-gcp      # Setup with GCP Vertex AI
make setup-ollama   # Setup with local Ollama
make setup-copilot  # Setup with GitHub Copilot
make status         # Show current configuration and service status
make stop           # Stop LiteLLM proxy
make clean          # Stop services and remove all configuration
```


## How To Proceed

- This repository contains a flexible multi-provider setup for Claude Code inside a devcontainer.
- The setup supports GCP Vertex AI (for corporate compliance), local Ollama (for offline work), and GitHub Copilot (for existing subscriptions).
- To integrate it with your code base, transfer the following files to your project:
  - `.devcontainer/` folder (entire directory)
  - `Makefile`
- Review the setup to assess that it meets your required security standards before use.

## Additional Resources

- For AI agents and detailed technical documentation, see `README-claude.md`
- For LiteLLM configuration examples, see `litellm/config.*.yaml`
- For environment configuration, see `.devcontainer/sample.env` (comprehensive template with all variables)

Happy Coding.
