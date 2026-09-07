.DEFAULT_GOAL := help

# -------------------------------------------------------------------------
.PHONY: help
help: ## This help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: lint
lint: ## Run linters
	uv run ruff check . --fix
	uv run ruff format .
	uv run typos .

.PHONY: mypy
mypy: ## Run mypy type checks
	uv run mypy --config-file pyproject.toml .

