.DEFAULT_GOAL := help
.PHONY: help setup-gcp setup-ollama setup-copilot status stop clean

# Configuration
DEVCONTAINER_DIR := .devcontainer
ENV_FILE := $(DEVCONTAINER_DIR)/.env
CLAUDE_SETTINGS := $(HOME)/.claude/settings.json
PID_FILE := /tmp/litellm.pid

help: ## Show this help message
	@echo "Claude Code Multi-Provider Setup"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Usage:"
	@echo "  1. Choose your provider: make setup-gcp|setup-ollama|setup-copilot"
	@echo "  2. Check status: make status"
	@echo "  3. Stop services: make stop"

setup-gcp: ## Setup Claude Code with GCP Vertex AI
	@echo "🔧 Setting up Claude Code with GCP Vertex AI..."
	@$(MAKE) _check_gcloud
	@$(MAKE) _setup_env PROFILE=gcp
	@$(MAKE) _authenticate_gcp
	@$(MAKE) _setup_claude_config
	@$(MAKE) _start_litellm
	@echo "✅ GCP setup complete!"
	@echo "   Run 'make status' to verify"

setup-ollama: ## Setup Claude Code with local Ollama
	@echo "🔧 Setting up Claude Code with Ollama..."
	@$(MAKE) _check_ollama
	@$(MAKE) _setup_env PROFILE=ollama
	@$(MAKE) _setup_claude_config
	@$(MAKE) _start_litellm
	@echo "✅ Ollama setup complete!"
	@echo "   Run 'make status' to verify"

setup-copilot: ## Setup Claude Code with GitHub Copilot
	@echo "🔧 Setting up Claude Code with GitHub Copilot..."
	@$(MAKE) _check_copilot
	@$(MAKE) _setup_env PROFILE=copilot
	@$(MAKE) _setup_claude_config
	@$(MAKE) _start_litellm
	@echo "✅ GitHub Copilot setup complete!"
	@echo "   Run 'make status' to verify"

status: ## Show current profile and service status
	@echo "📊 Claude Code Status"
	@echo ""
	@if [ -f "$(ENV_FILE)" ]; then \
		echo "Active Profile: $$(grep '^PROFILE=' $(ENV_FILE) | cut -d'=' -f2)"; \
		echo "LiteLLM Config: $$(grep '^LITELLM_CONFIG=' $(ENV_FILE) | cut -d'=' -f2)"; \
	else \
		echo "❌ No profile configured. Run 'make setup-<provider>'"; \
	fi
	@echo ""
	@if [ -f "$(PID_FILE)" ]; then \
		PID=$$(cat $(PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "✅ LiteLLM Proxy: Running (PID $$PID)"; \
			echo "   Endpoint: http://localhost:$$(grep '^LITELLM_PORT=' $(ENV_FILE) | cut -d'=' -f2)"; \
		else \
			echo "❌ LiteLLM Proxy: Not running (stale PID)"; \
			rm -f $(PID_FILE); \
		fi \
	else \
		echo "❌ LiteLLM Proxy: Not running"; \
	fi
	@echo ""
	@if [ -f "$(CLAUDE_SETTINGS)" ]; then \
		echo "✅ Claude Config: $(CLAUDE_SETTINGS)"; \
	else \
		echo "❌ Claude Config: Not found"; \
	fi

stop: ## Stop LiteLLM proxy
	@echo "🛑 Stopping LiteLLM proxy..."
	@if [ -f "$(PID_FILE)" ]; then \
		PID=$$(cat $(PID_FILE)); \
		if ps -p $$PID > /dev/null 2>&1; then \
			kill $$PID && echo "✅ LiteLLM stopped"; \
		else \
			echo "⚠️  LiteLLM not running"; \
		fi; \
		rm -f $(PID_FILE); \
	else \
		echo "⚠️  No PID file found"; \
	fi

clean: ## Stop services and remove all configuration
	@echo "🧹 Cleaning up..."
	@$(MAKE) stop
	@rm -f $(ENV_FILE)
	@rm -f $(CLAUDE_SETTINGS)
	@echo "✅ Cleanup complete"

# Internal targets
_check_gcloud:
	@if ! command -v gcloud > /dev/null 2>&1; then \
		echo "❌ Error: gcloud CLI not found"; \
		exit 1; \
	fi

_check_ollama:
	@if ! curl -s http://host.docker.internal:11434/api/tags > /dev/null 2>&1; then \
		echo "❌ Error: Ollama not running on host"; \
		echo "   Start it on your host machine with: ollama serve"; \
		echo "   (Ollama must run on the host, not in the container)"; \
		exit 1; \
	fi
	@echo "✅ Ollama is running on host"

_check_copilot:
	@echo "⚠️  Ensure you're logged in to GitHub Copilot in VS Code"

_setup_env:
	@echo "  → Configuring environment for $(PROFILE)..."
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "  → Creating $(ENV_FILE) from sample.env..."; \
		cp $(DEVCONTAINER_DIR)/sample.env $(ENV_FILE); \
		sed -i 's/LITELLM_CONFIG=.*/LITELLM_CONFIG=config.$(PROFILE).yaml/' $(ENV_FILE); \
		sed -i 's/PROFILE=.*/PROFILE=$(PROFILE)/' $(ENV_FILE); \
		echo "  → Created $(ENV_FILE) for $(PROFILE) profile"; \
		if [ "$(PROFILE)" = "gcp" ]; then \
			echo "  ⚠️  IMPORTANT: Edit $(ENV_FILE) and set your GCP_PROJECT_ID"; \
		fi; \
		echo "  ⚠️  Also update LITELLM_MASTER_KEY with a random value"; \
		echo "     Generate one with: openssl rand -hex 32"; \
		read -p "  Press Enter when ready to continue..."; \
	else \
		echo "  ⚠️  $(ENV_FILE) exists. Updating profile to $(PROFILE)..."; \
		sed -i 's/LITELLM_CONFIG=.*/LITELLM_CONFIG=config.$(PROFILE).yaml/' $(ENV_FILE); \
		sed -i 's/PROFILE=.*/PROFILE=$(PROFILE)/' $(ENV_FILE); \
		echo "  → Updated $(ENV_FILE) to use $(PROFILE) profile"; \
	fi

_authenticate_gcp:
	@echo "  → Authenticating with GCP..."
	@. $(ENV_FILE) && gcloud config set project $$GCP_PROJECT_ID
	@gcloud auth application-default login
	@echo "  ✅ GCP authentication complete"

_setup_claude_config:
	@echo "  → Configuring Claude Code..."
	@mkdir -p $(HOME)/.claude
	@. $(ENV_FILE) && \
	printf '{\n  "env": {\n    "ANTHROPIC_BASE_URL": "http://localhost:%s",\n    "ANTHROPIC_AUTH_TOKEN": "%s",\n    "ANTHROPIC_MODEL": "sonnet",\n    "ANTHROPIC_DEFAULT_OPUS_MODEL": "opus",\n    "ANTHROPIC_DEFAULT_SONNET_MODEL": "sonnet",\n    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "haiku",\n    "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet",\n    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "true"\n  }\n}\n' "$$LITELLM_PORT" "$$LITELLM_MASTER_KEY" > $(CLAUDE_SETTINGS)
	@echo "  ✅ Claude config written to $(CLAUDE_SETTINGS)"

_start_litellm:
	@echo "  → Starting LiteLLM proxy..."
	@$(MAKE) stop > /dev/null 2>&1 || true
	@. $(ENV_FILE) && \
	nohup litellm --config litellm/$$LITELLM_CONFIG \
		--port $$LITELLM_PORT \
		--master-key $$LITELLM_MASTER_KEY \
		> /tmp/litellm.log 2>&1 & echo $$! > $(PID_FILE)
	@echo "  → Waiting for LiteLLM to be ready..."
	@for i in 1 2 3 4 5; do \
		sleep 1; \
		if curl -s http://localhost:$$(. $(ENV_FILE) && echo $$LITELLM_PORT)/health > /dev/null 2>&1; then \
			echo "  ✅ LiteLLM started and healthy (PID $$(cat $(PID_FILE)))"; \
			exit 0; \
		fi; \
	done; \
	if ps -p $$(cat $(PID_FILE)) > /dev/null 2>&1; then \
		echo "  ⚠️  LiteLLM started but not responding yet. Check /tmp/litellm.log"; \
	else \
		echo "  ❌ Failed to start LiteLLM. Check /tmp/litellm.log"; \
		exit 1; \
	fi
