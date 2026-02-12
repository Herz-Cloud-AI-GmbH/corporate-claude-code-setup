# Corporate Claude-Code Setup

## Pain Points To Solve
- Typically, developers in corporate environments cannot just use their private Claude Code subscriptions, but would like to make use of the power of Claude Code.
- If developers work on multiple projects, it can be preferable to have Claude Code installed in a project specific environment. Some projects might allow the use of AI assisted coding and others don't.
- Often companies don't have a direct contract with Anthropic for Claude Code but have existing cloud infrastructure.

## Solution
- This repository shows a setup of Claude Code within a devcontainer. This ensures to keep the installation project local.
- The setup supports **two different LLM providers**:
  - **GCP Vertex AI (native)**: Claude Code connects directly to Vertex AI (simplest, no proxy).
  - **GitHub Copilot subscription (via LiteLLM)**: Consume Claude models through Copilot.
- You can interactively choose which provider to use via simple `make` commands.

## Prerequisites

1. This repository was written with Cursor, which is able to run devcontainers. If you use another IDE, this IDE must have the capabilities to run devcontainers.
2. Choose one of the following providers:
   - **For GCP Vertex AI**: Access to a project in Google Cloud with Vertex AI enabled
   - **For GitHub Copilot**: Active GitHub Copilot subscription

## Devcontainer Setup

### Dockerfile

- The devcontainer setup is configured in the folder `.devcontainer`.
- As base image a devcontainer `node` image is used to have `npm` available for running MCP servers with `npx` later on.
- `gcloud` is installed to be able to login to Google Cloud (for GCP Vertex AI provider).
- `LiteLLM` is installed (used only for Copilot provider mode).
- `uv` is installed to have `uvx` available to run MCP servers later on.

### devcontainer.json

- Inside the `devcontainer.json` the configuration of the devcontainer is done.
- Important is the mount of the local `~/.ssh` folder to be able to push to the remote repository within the devcontainer with the same ssh setup from the local PC.
- To easily distinguish if the project is opened locally or inside the devcontainer, a custom coloring of the top-bar, side-bar, and bottom is added inside the `devcontainer.json`. This custom coloring is active when the project is opened inside the devcontainer.
- Port 4000 is forwarded for the LiteLLM proxy (used in Copilot mode).

### LiteLLM Configuration Files

- LiteLLM configuration file defines routing to GitHub Copilot (located in `litellm/`):
  - `config.copilot.yaml` - Routes to GitHub Copilot
- The config defines three model aliases (`opus`, `sonnet`, `haiku`) for different use cases (proxy mode only).

## Google Cloud Setup

### GCP Project & Permissions
- You need to have access to a GCP Project.
- Inside that project you need to have the permission `Vertex AI User`.

### Vertex AI Configuration
- Inside Vertex AI go to Model Garden
- Enable endpoints for Claude models:
  - **Claude Opus**: `claude-opus-4-5@20251101` - specified as `ANTHROPIC_DEFAULT_OPUS_MODEL`
  - **Claude Sonnet**: `claude-sonnet-4-5@20250929` - specified as `ANTHROPIC_DEFAULT_SONNET_MODEL`
  - **Claude Haiku**: `claude-haiku-4-5@20250925` - specified as `ANTHROPIC_DEFAULT_HAIKU_MODEL`
- The model IDs of your activated Claude models need to be entered in the `.env` file.

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
- You will be prompted to set your GCP project ID if missing
- The setup will authenticate you to Google Cloud via browser
- Click on the authentication link with `Command + click` and follow the instructions
- In this mode, Claude Code uses **native Vertex AI** (no LiteLLM).

#### Option B: GitHub Copilot
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
make stop              # Stop LiteLLM proxy (if you are in a proxy mode)
make setup-<provider>  # Start new provider (gcp or copilot)
```

## Available Commands

All setup is managed via the `Makefile`:

```bash
make help           # Show all available commands
make setup-gcp      # Setup with GCP Vertex AI
make setup-copilot  # Setup with GitHub Copilot
make status         # Show current configuration and service status
make stop           # Stop LiteLLM proxy
make clean          # Stop services and remove all configuration
```


## How To Proceed

- This repository contains a flexible multi-provider setup for Claude Code inside a devcontainer.
- The setup supports GCP Vertex AI (for corporate compliance) and GitHub Copilot (for existing subscriptions).
- To integrate it with your code base, transfer the following files to your project:
  - `.devcontainer/` folder (entire directory)
  - `Makefile`
- Review the setup to assess that it meets your required security standards before use.

## Additional Resources

- For AI agents and detailed technical documentation, see `AGENTS.md`
- For LiteLLM configuration examples, see `litellm/config.*.yaml`
- For environment configuration, see `.devcontainer/sample.env` (comprehensive template with all variables)

Happy Coding.
