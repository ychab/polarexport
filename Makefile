.DEFAULT_GOAL := help


################
# Help
################

.PHONY: help
help:
	@grep -E '^[a-zA-Z0-9 -]+:.*## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'


##############
# Dependencies
##############

.PHONY: install install-deps install-precommit update update-deps update-precommit lock outdated

install-deps:  ## Install python dependencies
	uv sync --all-groups

install-precommit:  ## Install pre-commit hooks
	uv run pre-commit install

install: install-deps install-precommit ## Install python dependencies and pre-commit hooks

update-deps:  ## Update python dependencies
	uv lock --upgrade
	uv sync --all-groups

update-precommit:  ## Update pre-commit hooks
	uv run pre-commit autoupdate

update: update-deps update-precommit ## Update python dependencies and pre-commit hooks

lock:  ## Lock dependencies
	uv lock

outdated: ## List outdated dependencies
	uv pip list --outdated


############
# Versioning
############

BUMP_TARGETS = bump-patch bump-minor bump-major

# This "phantom" target exists only to appear in 'make help'
bump: ## Bump version (options: bump-patch, bump-minor, bump-major)

.PHONY: $(BUMP_TARGETS) bump
$(BUMP_TARGETS): bump-%:
	uvx bump-my-version bump $*
	uv sync


########
# Docker
########

.PHONY: ps logs up up-wiremock down restart reload reset

ps:  ## List containers
	docker compose ps --all

logs:  ## Show container logs
	docker compose logs -f

up: up-wiremock ## Start containers

up-wiremock:  ## Start the WireMock container only
	docker compose up --detach --wait wiremock-polar

down: ## Stop containers
	docker compose down --remove-orphans

restart: ## Restart containers
	docker compose restart

reload: down up ## Stop and start containers

reset:  ## Remove volumes and images
	docker compose down --remove-orphans --volumes --rmi local


#####
# App
#####

.PHONY: run

run: ## Show the CLI help
	uv run polarexport --help


################
# Testing
################

.PHONY: test test-unit test-integration

test: up-wiremock ## Run all the testsuite
	uv run pytest ./tests -n auto --dist=loadgroup || ($(MAKE) down && exit 1)
	@$(MAKE) down

test-unit: ## Run unit tests (no Docker required)
	uv run pytest ./tests/unit -n auto --dist=loadgroup -v

test-integration: up-wiremock ## Run integration tests
	uv run pytest ./tests/integration -n auto --dist=loadgroup -v || ($(MAKE) down && exit 1)
	@$(MAKE) down


###################
# Local Development
###################

.PHONY: lint lint-format lint-check precommit clean

lint-format:  ## Lint and format code
	uv run ruff check polarexport tests
	uv run ruff format polarexport tests
	uv run mypy
	uv run deptry .

lint: lint-format

lint-check: ## Lint and check code
	uv run ruff check --no-fix polarexport tests
	uv run ruff format --check polarexport tests
	uv run mypy
	uv run deptry .

precommit: ## Run pre-commit hooks
	uv run pre-commit run --all-files

clean: ## Cleanup cache files
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov coverage.xml junit.xml
	rm -f .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
