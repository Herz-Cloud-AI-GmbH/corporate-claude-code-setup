.DEFAULT_GOAL := help
.PHONY: help script-help setup-gcp setup-copilot status stop-litellm clean start-litellm

# Delegate all logic to the Python script
SCRIPT := python3 scripts/manage.py

help: ## Show this help message
	@echo "Claude Code devcontainer setup"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make setup-gcp"
	@echo "  make setup-copilot"
	@echo "  make status"

script-help: ## Show underlying scripts/manage.py help
	@$(SCRIPT) --help

setup-gcp: ## Setup Claude Code with GCP Vertex AI
	@$(SCRIPT) setup gcp

setup-copilot: ## Setup Claude Code with GitHub Copilot
	@$(SCRIPT) setup copilot

start-litellm: ## Start LiteLLM proxy (uses existing config)
	@$(SCRIPT) start

stop-litellm: ## Stop LiteLLM proxy
	@$(SCRIPT) stop

status: ## Show current profile and service status
	@$(SCRIPT) status

clean: ## Remove configuration and stop services
	@$(SCRIPT) stop
	@rm -f .devcontainer/.env
	@rm -f ~/.claude/settings.json
	@echo "✅ Cleanup complete"
