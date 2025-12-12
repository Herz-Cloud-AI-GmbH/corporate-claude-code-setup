# Corporate Claude-Code Setup

## Pain Points To Solve
- Typically developers in corporate environments cannot just use their private Claude Code subscription but would like to make use of the power of Claude Code.
- If developers work on multiple projects it can be preferable to have Claude Code installed in a project specific environment only because some project might allow the use of AI assisted coding and don't due to confidentiality restrictions.
- Often companies don't have a direct contract with Anthropic for Claude Code but have existing cloud infrastructure.

## Solution
- This repository shows a setup of Claude Code within a devcontainer. This ensures to keep the installation project local.
- Additionally, the Claude Sonnet models are configured not to be used from Anthropic directly but to be consumed from Vertex AI inside a GCP Project. If the company has a corporate GCP cloud landing zone, this ensures compliant usage of Anthropic models.

## Prerequisites

1. This repository was written with Cursor, which is able to run devcontainers. If you use another IDE, this IDE must have the capabilities to run devcontainers.
2.  The Anthropic models are assumed to be served through Google Cloud, which means that you ned to have access to a project in Google Cloud.

## Devcontainer Setup

### Dockerfile

- The devcontainer setup is configured in the folder `.devcontainer`.
- As base image a devcontainer `node` image is used to have `npm` available for running MCP servers with `npx` later on.
- `gcloud` is installed to be abel to login to Google Cloud.
- `uv` is installed to have `uvx` available to run MCP servers later on.

### devcontainer.json

- Inside the `devcontainer.json` the configuration of the devcontainer is done.
- Important is the mount of the local `~/.ssh` folder to be able to push to the remote repository within the devcontainer with the same ssh setup from the local PC.
- To easily distinguish if the project is opened locally or inside the devcontainer, a custom coloring of the top-bar, side-bar, and bottom is added inside the `devcontainer.json`. This custom coloring is active when the project is opened inside the devcontainer.

### gcloud_login.sh

- The `gloud_login.sh` script handles the authentication to Google Cloud.
- It is executed as `postStartCommand`, i.e., every time when the devcontainer has started again.

## Google Cloud Setup

### GCP Project & Permissions
- You need to have access to a GCP Project.
- Inside that project you need to have the permission `Vertex AI User`.

### Vertex AI Configuration
- Inside Vertex AI go to Model Garden
- Enable an endpoint for the latest Claude Sonnet model.
  - At the time of creating this Readme, the latest version was `claude-sonnet-4-5@20250929`.
  - The model id of your activated Claude Sonnet model needs to entered later in the `.env` file.
  - The Claude Sonnet model is later specified in the `.env` file as the `ANTHROPIC_MODEL`.
- Similarly enable an endpoint for the latest Claude Haiku model.
  - This model is later specified in the `.env` file as the `ANTHROPIC_SMALL_FAST_MODEL`.
  - At the time of creating this Readme, the latest version was `claude-haiku-4-5@20251001`.

## How To Use This Repository

### Cloning
1. Clone the repository to your machine

### .env Configuration
2. Copy `.devcontainer/sample.env` to `.devcontainer/.env` and fill in the required variables:
  2.1 The GCP project id is needed for `GCP_PROJECT_ID` and `ANTHROPIC_VERTEX_PROJECT_ID`.
  2.2 The concrete model ids of the deployed Models in Vertex AI Model Garden needs to be entered in `ANTHROPIC_MODEL` and `ANTHROPIC_SMALL_FAST_MODEL`. Typically, a Claude Sonnet Model is used for `ANTHROPIC_MODEL` and a CLaude Haiku model for `ANTHROPIC_SMALL_FAST_MODEL`.

### Build Devcontainer
3. Go to the command palette of Cursor or Vscode with with `Shift + Command + P` or `F1`and run `Reopen Devcontainer`.
4. Once this command is done, the image is built and the devcontainer is started.

### GCP Login
5. At the very end of the devcontainer build process you see in the terminal a request to authenticate to Google Cloud. To do this, click on the link with `command + click`.
6. Follow the instructions in the browser and paste the authentication token back into the terminal. Once this is done, you are authenticated to your GCP project and Claude Code is able to connect to the deployed endpoints in your GCP project.

### Run Claude Code
7. Now should be abel to open a terminal in `vscode`or `cursor`and to type in `claude`. Et voilá, Claude Code is starting, ready to be your helpful coding assistant.
