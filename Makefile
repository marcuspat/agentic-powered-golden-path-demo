.DEFAULT_GOAL := help

# âââ Directories ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
AGENT_DIR     := ai-onboarding-agent
SRC_DIR       := src
SCRIPTS_DIR   := scripts
VENV          := .venv
PYTHON        := $(VENV)/bin/python3
PIP           := $(VENV)/bin/pip

# âââ Colours ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
BLUE  := \033[0;34m
GREEN := \033[0;32m
RESET := \033[0m

.PHONY: help setup bootstrap preflight demo demo-request test lint status clean

## ââ Entry Points ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

help: ## Show this help
	@printf '$(BLUE)Golden Path AI-Powered Developer Onboarding$(RESET)\n\n'
	@printf 'Usage: make [target]\n\n'
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-18s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@printf 'Quick start:\n'
	@printf '  1. make setup       â install deps + download idpbuilder\n'
	@printf '  2. Set GITHUB_TOKEN, GITHUB_USERNAME, OPENROUTER_API_KEY\n'
	@printf '  3. make bootstrap   â spin up KinD cluster with ArgoCD\n'
	@printf '  4. make demo        â run the full AI onboarding demo\n'

## ââ Setup âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

setup: ## Install Python deps, download idpbuilder, verify prerequisites
	@bash $(SCRIPTS_DIR)/setup.sh

bootstrap: ## Create idpbuilder KinD cluster (ArgoCD + Tekton)
	@echo "$(BLUE)Bootstrapping IDP cluster...$(RESET)"
	@./idpbuilder create
	@echo "$(GREEN)â Cluster ready. Run 'make status' to verify.$(RESET)"

## ââ Pre-flight ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

preflight: ## Validate env vars and cluster readiness before demo
	@bash $(SCRIPTS_DIR)/preflight.sh

## ââ Demo ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

demo: preflight ## Run the full end-to-end AI onboarding demo
	@echo "$(BLUE)Running Golden Path demo...$(RESET)"
	@cd $(AGENT_DIR) && bash demo.sh demo

demo-request: preflight ## Run agent with custom request (REQUEST="your request")
ifndef REQUEST
	$(error Set REQUEST variable: make demo-request REQUEST="Deploy my service called my-api")
endif
	@echo "$(BLUE)Processing: $(REQUEST)$(RESET)"
	@cd $(AGENT_DIR) && $(PYTHON) agent.py "$(REQUEST)" 2>&1 || \
		python3 agent.py "$(REQUEST)"

demo-interactive: preflight ## Run interactive demo mode
	@cd $(AGENT_DIR) && bash interactive-demo.sh

## ââ Testing âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

test: ## Run full test suite (pytest)
	@echo "$(BLUE)Running test suite...$(RESET)"
	@if [ -f $(PYTHON) ]; then \
		$(PYTHON) -m pytest $(SRC_DIR)/ $(AGENT_DIR)/ -v --tb=short 2>&1; \
	else \
		python3 -m pytest $(SRC_DIR)/ $(AGENT_DIR)/ -v --tb=short 2>&1; \
	fi

test-v1: ## Run v1 agent tests only
	@cd $(AGENT_DIR) && python3 -m pytest test_agent.py -v --tb=short

test-v2: ## Run v2 agent tests only
	@python3 -m pytest $(SRC_DIR)/test_agent.py $(SRC_DIR)/test_integration.py -v --tb=short

lint: ## Run ruff linter
	@python3 -m ruff check --select E,W,F,I --ignore E501 $(AGENT_DIR)/agent.py $(SRC_DIR)/

## ââ Status ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

status: ## Show cluster, ArgoCD, and pod status
	@echo "$(BLUE)=== Cluster Status ===$(RESET)"
	@./idpbuilder get status 2>/dev/null || echo "  idpbuilder cluster not running"
	@echo ""
	@echo "$(BLUE)=== ArgoCD Applications ===$(RESET)"
	@kubectl get applications -n argocd 2>/dev/null || echo "  ArgoCD not reachable"
	@echo ""
	@echo "$(BLUE)=== Running Pods (default ns) ===$(RESET)"
	@kubectl get pods -n default 2>/dev/null || echo "  No pods in default namespace"
	@echo ""
	@echo "$(BLUE)=== ArgoCD Access ===$(RESET)"
	@echo "  URL:      https://cnoe.localtest.me/argocd"
	@echo "  Username: admin"
	@printf "  Password: "; kubectl -n argocd get secret argocd-initial-admin-secret \
		-o jsonpath="{.data.password}" 2>/dev/null | base64 -d && echo || echo "(cluster not ready)"

argocd-password: ## Print the ArgoCD admin password
	@kubectl -n argocd get secret argocd-initial-admin-secret \
		-o jsonpath="{.data.password}" | base64 -d && echo

## ââ Cleanup âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ

clean: ## Tear down the idpbuilder KinD cluster
	@echo "$(BLUE)Deleting idpbuilder cluster...$(RESET)"
	@./idpbuilder delete
	@echo "$(GREEN)â Cluster deleted.$(RESET)"

clean-repos: ## List demo repos created during testing (manual delete required)
	@echo "$(BLUE)GitHub repos matching *-source and *-gitops:$(RESET)"
	@gh repo list --limit 50 --json name -q '.[] | .name' 2>/dev/null | grep -E '(-source|-gitops)$$' || \
		echo "  Install 'gh' CLI or delete repos manually at https://github.com/$(GITHUB_USERNAME)"

clean-venv: ## Remove the Python virtual environment
	@rm -rf $(VENV)
	@echo "$(GREEN)â .venv removed.$(RESET)"
