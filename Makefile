# Golden Path AI-Powered Onboarding — root Makefile.
#
# All Python invocations use ``python3`` so we don't depend on a venv being
# active; CI and local devs can both run the same recipes. Tabs (not spaces)
# indent every recipe — Make insists on that.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON ?= python3
PIP    ?= $(PYTHON) -m pip
PYTEST ?= $(PYTHON) -m pytest

REPO_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS   := $(REPO_ROOT)/scripts

.DEFAULT_GOAL := help

.PHONY: help bootstrap lint typecheck test test-unit test-integration test-e2e test-perf test-security secret-scan test-all validate bench clean agent-cli

help:  ## Show this help (default target).
	@awk 'BEGIN {FS = ":.*?## "; printf "Golden Path Make targets:\n\n"} \
	/^[a-zA-Z0-9_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap:  ## Install Python dev dependencies (pytest, ruff, mypy, pip-audit, …).
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt

lint:  ## Run ruff over agent/ and tests/.
	$(PYTHON) -m ruff check agent/ tests/

typecheck:  ## Run mypy over the agent/ package.
	$(PYTHON) -m mypy agent/

test:  ## Run unit + integration tiers (the PR gate).
	$(PYTEST) tests/unit tests/integration -q -m "not legacy"

test-unit:  ## Run only the unit tier (Tier 1).
	$(PYTEST) tests/unit -q -m "not legacy"

test-integration:  ## Run only the integration tier (Tier 2).
	$(PYTEST) tests/integration -q -m "not legacy"

test-e2e:  ## Run only the e2e tier (Tier 3); sets RUN_E2E=1.
	RUN_E2E=1 $(PYTEST) tests/e2e -q

test-perf:  ## Run only the performance tier (Tier 4).
	$(PYTEST) tests/performance -q

test-security:  ## Run only the security tier (Tier 5).
	$(PYTEST) tests/security -q

secret-scan:  ## Standalone credential scan over cnoe-stacks/ and agent/.
	$(PYTHON) -m tests.security._scanner_cli

test-all:  ## lint + typecheck + test + test-security; the release gate.
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) test-security

validate:  ## Run the full validation gauntlet via scripts/validate.sh.
	$(SCRIPTS)/validate.sh

bench:  ## Run perf benchmarks and print results.
	$(PYTEST) tests/performance -q --benchmark-enable 2>/dev/null || $(PYTEST) tests/performance -q

clean:  ## Remove pytest/ruff/mypy/__pycache__ caches.
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .mypy_cache .benchmarks .coverage htmlcov

agent-cli:  ## Convenience wrapper: `make agent-cli REQUEST="..."`.
	@if [ -z "$${REQUEST:-}" ]; then \
	  echo "Usage: make agent-cli REQUEST=\"onboard inventory-api\"" >&2; \
	  exit 2; \
	fi
	$(PYTHON) -m agent "$$REQUEST"
