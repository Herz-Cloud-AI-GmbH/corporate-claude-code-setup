.DEFAULT_GOAL := help
.PHONY: help setup-gcp setup-ollama setup-copilot status stop clean start

# Delegate all logic to the Python script
SCRIPT := python3 scripts/manage.py

help: ## Show this help message
	@$(SCRIPT) --help

setup-gcp: ## Setup Claude Code with GCP Vertex AI
	@$(SCRIPT) setup gcp

setup-ollama: ## Setup Claude Code with local Ollama
	@$(SCRIPT) setup ollama

setup-copilot: ## Setup Claude Code with GitHub Copilot
	@$(SCRIPT) setup copilot

start: ## Start LiteLLM proxy (uses existing config)
	@$(SCRIPT) start

stop: ## Stop LiteLLM proxy
	@$(SCRIPT) stop

status: ## Show current profile and service status
	@$(SCRIPT) status

clean: ## Remove configuration and stop services
	@$(SCRIPT) stop
	@rm -f .devcontainer/.env
	@rm -f ~/.claude/settings.json
	@echo "✅ Cleanup complete"
