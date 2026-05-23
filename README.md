# Golden Path — AI-Powered Developer Onboarding

A production-leaning reference implementation of an Internal Developer Platform
(IDP) agent that turns a one-line natural-language request into a fully provisioned
application: source repo, GitOps repo, Kubernetes manifests, and an ArgoCD
`Application` — with zero manual steps.

---

## Quick Start

```bash
# 1. Install Python dev dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 2. Set required environment variables
export GITHUB_TOKEN=<personal-access-token>
export GITHUB_USERNAME=<your-github-username>
export OPENROUTER_API_KEY=<openrouter-api-key>

# 3. Bring up the local platform (KinD + ArgoCD + Tekton)
./idpbuilder create

# 4. Onboard an application
python -m agent onboard "I need to deploy my new NodeJS service called inventory-api"
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.9+ | Tested on 3.9 and 3.12 |
| Docker | Required by idpbuilder / KinD |
| kubectl | Kubernetes CLI |
| idpbuilder | Bundled at `./idpbuilder` — spins up a local IDP cluster |
| GitHub Personal Access Token | Scopes: `repo`, `delete_repo` |
| OpenRouter API key | For LLM-powered intent extraction |

---

## CLI Reference

```
python -m agent [-h] [--version] [--validate-env] [--log-level LEVEL]
               {onboard,cleanup} ...
```

### `onboard`

```
python -m agent onboard [--no-llm] [--dry-run] [--actor ACTOR] "<request>"
```

| Flag | Description |
|---|---|
| `--dry-run` | Parse and validate only; make no external calls |
| `--no-llm` | Use regex extractor instead of OpenRouter |
| `--actor ACTOR` | Identity of the requester for audit logs |

**Exit codes:** `0` success · `1` provisioning failure · `2` cancelled / usage error

**Examples:**

```bash
# Full live onboarding
python -m agent onboard "Deploy my payment-processor service"

# Validate intent parsing without touching any external system
python -m agent onboard "Create a user-management service" --dry-run --no-llm

# Check that environment variables are present
python -m agent --validate-env
```

### `cleanup`

```
python -m agent cleanup [--repos] [--keep-namespace] [--namespace NS] [--actor ACTOR] <app-name>
```

| Flag | Description |
|---|---|
| `--repos` | Also delete the source + GitOps GitHub repositories |
| `--keep-namespace` | Do not delete the Kubernetes namespace |
| `--namespace NS` | Override the namespace (default: `<app-name>`) |

**Example:**

```bash
python -m agent cleanup inventory-api --repos
```

### Back-compat invocation

Passing a bare string without a subcommand routes to `onboard`:

```bash
python -m agent "I need a checkout-service"
```

---

## Architecture

The agent is structured as a layered hexagonal application under `agent/`:

```
agent/
├── domain/                  # Core business rules — no external dependencies
│   ├── aggregates/          # OnboardingRun, SourceRepository, GitOpsRepository,
│   │                        # ArgoApplication, Stack
│   ├── services/            # Intent extraction, orchestration, stack selection,
│   │                        # template rendering
│   ├── ports.py             # Abstract interfaces (Protocols)
│   ├── events.py            # Domain events
│   ├── values.py            # Value objects
│   └── errors.py            # Domain exceptions
├── application/             # Use-case orchestrators
│   ├── onboarding.py        # OnboardingApplicationService
│   ├── cleanup.py           # CleanupApplicationService
│   └── rollback.py          # RollbackApplicationService
├── infrastructure/          # Concrete adapters
│   ├── github/              # GitHub repo creation, source & GitOps wiring
│   ├── git/                 # Local git clone / commit / push
│   ├── k8s/                 # Kubernetes / ArgoCD adapter
│   ├── catalog/             # Stack template filesystem loader
│   └── events/              # JSONL event emitter
├── composition.py           # Dependency wiring (pure function, no framework)
└── cli.py                   # Argparse entry point
```

**Dependency rule:** `infrastructure` → `domain` ← `application`. Neither
infrastructure nor application layers may import from each other.

### Workflow

```
Developer request  ──▶  Intent extraction  ──▶  Stack selection
                                                      │
                                         Template rendering (Jinja2)
                                                      │
                              ┌───────────────────────┤
                              ▼                       ▼
                        Source repo               GitOps repo
                     (GitHub + local git)     (GitHub + local git)
                                                      │
                                              ArgoCD Application
                                                      │
                                         Kubernetes reconciliation
```

---

## Stack Templates (`cnoe-stacks/`)

```
cnoe-stacks/
├── nodejs-template/           # Application source template
│   ├── app-source/
│   │   ├── index.js           # HTTP server
│   │   ├── package.json
│   │   ├── Dockerfile
│   │   └── k8s/               # Namespace, NetworkPolicy, ResourceQuota,
│   │                          # ExternalSecret, ServiceMonitor
│   └── .tekton/               # Tekton Pipeline + PipelineRun
└── nodejs-gitops-template/    # GitOps manifests
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── configmap.yaml
    ├── kustomization.yaml
    └── app.yaml               # ArgoCD Application CR
```

No plaintext secrets appear in any template. Sensitive values are wired through
`ExternalSecret` CRs that pull from an external secrets store at runtime.

---

## Development Workflow

```bash
# Install all dev tools (pytest, ruff, mypy, pip-audit, …)
make bootstrap

# Run the full gate before opening a PR
make lint         # ruff — 0 issues expected
make typecheck    # mypy — 0 issues expected
make test         # unit + integration (156 tests)
make test-security # dependency audit + credential scan + RBAC checks
make secret-scan  # standalone credential scan over agent/ and cnoe-stacks/

# Or run everything at once
make test-all     # lint + typecheck + test + test-security

# Full validation gauntlet (mirrors CI)
scripts/validate.sh

# Performance micro-benchmarks
make test-perf

# End-to-end tier (requires live KinD cluster + GitHub + OpenRouter)
RUN_E2E=1 make test-e2e
```

### CI

GitHub Actions runs the full gate on every push/PR to `main`:

| Stage | Command | Status |
|---|---|---|
| Lint | `make lint` (ruff) | Enforced |
| Typecheck | `make typecheck` (mypy) | Enforced |
| Unit + Integration | `make test` | Enforced |
| Security | `make test-security` | Enforced |
| Secret scan | `make secret-scan` | Enforced |

Matrix: Python 3.9 and 3.12 on ubuntu-latest.

---

## Test Architecture

| Tier | Location | Command | Description |
|---|---|---|---|
| 1 — Unit | `tests/unit/` | `make test-unit` | Pure functions, no I/O |
| 2 — Integration | `tests/integration/` | `make test-integration` | Jinja2, Git subprocess, mocked GitHub |
| 3 — E2E | `tests/e2e/` | `make test-e2e` | Live cluster (gated, `RUN_E2E=1`) |
| 4 — Performance | `tests/performance/` | `make test-perf` | Micro-benchmarks |
| 5 — Security | `tests/security/` | `make test-security` | Dep audit, secret scan, RBAC |

---

## Local Platform Setup

```bash
# Spin up KinD cluster with ArgoCD + Tekton
./idpbuilder create

# Check status
./idpbuilder get status

# ArgoCD dashboard: https://cnoe.localtest.me/argocd
# Username: admin
# Password:
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Stop cluster when done
./idpbuilder delete
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | PAT with `repo` + `delete_repo` scopes |
| `GITHUB_USERNAME` | Yes | Your GitHub username |
| `OPENROUTER_API_KEY` | Yes (unless `--no-llm`) | OpenRouter API key |
| `KUBECONFIG` | No | Path to kubeconfig (default: `~/.kube/config`) |

```bash
# Verify all required variables are set
python -m agent --validate-env
```

---

## Access Points

| Service | URL | Notes |
|---|---|---|
| ArgoCD | `https://cnoe.localtest.me/argocd` | Managed by idpbuilder |
| Deployed apps | `http://<app-name>.cnoe.localtest.me` | Via ingress |

---

## What the Golden Path Delivers

- **Zero manual steps** for a standard onboarding — one request provisions the
  source repo, the GitOps repo, and the ArgoCD Application.
- **Complete GitOps workflow** — two-repo pattern with ArgoCD reconciliation.
- **Production-leaning Kubernetes manifests** — namespace isolation, network
  policies, resource quotas, ExternalSecret references (no plaintext secrets in
  git), and a ServiceMonitor for observability.
- **Layered, tested architecture** — domain / application / infrastructure
  separation with unit, integration, security, and performance test tiers.
- **Extensible by design** — add stack templates, swap LLM providers, or wire
  alternative VCS backends without touching domain logic.

> End-to-end timing and success-rate figures depend on your cluster, network,
> and upstream GitHub / OpenRouter latency. Run `make test-perf` for the
> in-repo performance budgets; capture live metrics from your own environment
> before quoting them.

---

## Documentation

| Document | Description |
|---|---|
| [`docs/adr/`](docs/adr/) | 20 Architecture Decision Records |
| [`docs/ddd/`](docs/ddd/) | 12 Domain-Driven Design documents + context map |
| [`docs/USE-CASE-GUIDE.md`](docs/USE-CASE-GUIDE.md) | Persona-based usage guide |
| [`docs/VALIDATION-REPORT.md`](docs/VALIDATION-REPORT.md) | Captured command outputs and gate results |
| [`docs/testing-strategy.md`](docs/testing-strategy.md) | Test tier rationale and structure |
| [`docs/gitops-integration-workflow.md`](docs/gitops-integration-workflow.md) | GitOps workflow deep-dive |
| [`docs/monitoring-observability-strategy.md`](docs/monitoring-observability-strategy.md) | Observability approach |

---

## Project Structure

```
agentic-powered-golden-path-demo/
├── agent/                        # Main agent package (python -m agent)
│   ├── domain/                   # Business rules and domain model
│   ├── application/              # Use-case orchestrators
│   ├── infrastructure/           # External adapters (GitHub, k8s, git)
│   ├── composition.py            # Dependency wiring
│   └── cli.py                    # Argparse entry point
├── cnoe-stacks/                  # Jinja2 application templates
│   ├── nodejs-template/          # Node.js source + Tekton pipeline
│   └── nodejs-gitops-template/   # Kubernetes / ArgoCD manifests
├── tests/                        # Five-tier test suite
│   ├── unit/                     # Tier 1 — pure unit tests
│   ├── integration/              # Tier 2 — integration tests
│   ├── e2e/                      # Tier 3 — live cluster tests (RUN_E2E=1)
│   ├── performance/              # Tier 4 — benchmarks
│   └── security/                 # Tier 5 — dep audit + secret scan
├── docs/                         # Architecture and design documentation
│   ├── adr/                      # 20 Architecture Decision Records
│   └── ddd/                      # 12 DDD documents
├── scripts/                      # validate.sh — full local gate
├── .github/workflows/ci.yml      # GitHub Actions CI
├── .pre-commit-config.yaml       # Pre-commit hooks (ruff + secret-scan)
├── Makefile                      # Developer workflow targets
├── pyproject.toml                # Ruff, mypy, pytest configuration
├── requirements.txt              # Runtime dependencies
├── requirements-dev.txt          # Dev/test dependencies
└── idpbuilder                    # Local IDP cluster launcher (KinD + ArgoCD)
```

---

## Troubleshooting

**`Missing env vars: ['GITHUB_TOKEN', ...]`**
```bash
export GITHUB_TOKEN=<token>
export GITHUB_USERNAME=<username>
export OPENROUTER_API_KEY=<key>
python -m agent --validate-env   # should exit 0
```

**Cluster not running**
```bash
./idpbuilder create              # start
./idpbuilder get status          # check
kubectl cluster-info             # verify kubectl connectivity
```

**ArgoCD application not syncing**
```bash
argocd app list
argocd app sync <app-name> --force
argocd app logs <app-name>
```

**Token scope errors**
```bash
# Verify token has repo + delete_repo scopes
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
```
