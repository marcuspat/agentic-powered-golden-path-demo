# 🚀 Agentic Golden Path — AI-Powered Developer Onboarding

> **Say what you want to deploy. Watch it appear in ArgoCD.**

Natural language in → GitHub repos created → Kubernetes workload running → ArgoCD synced. Under 2 minutes\*, zero manual steps.

<sub>\* Timing is for the `make demo` onboarding flow itself, once the cluster is already running. One-time cluster bootstrap (`make bootstrap`) takes ~3 min separately — see Quick Start below.</sub>

[![CI](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

---

## ⚡ Quick Start — Three Commands

```bash
git clone https://github.com/adventurewave-labs/agentic-powered-golden-path-demo.git
cd agentic-powered-golden-path-demo

make setup      # downloads idpbuilder, creates Python venv, installs deps
make bootstrap  # spins up KinD cluster with ArgoCD + Tekton + Nginx (~3 min)
```

Set your credentials:

```bash
export GITHUB_TOKEN=ghp_...
export GITHUB_USERNAME=your-username
export OPENROUTER_API_KEY=sk-or-...
```

Then run the demo:

```bash
make preflight  # 8 pre-flight checks (cluster, ArgoCD, GitHub API, deps)
make demo       # AI agent onboards a new developer app end-to-end
```

That's it. Watch ArgoCD at **https://cnoe.localtest.me/argocd** as the app deploys itself.

---

## 🗺️ How It Works

```
Developer: "I need to deploy my inventory-api service"
                        │
                        ▼
              ┌─────────────────┐
              │  OpenRouter LLM  │  ← extracts app name from natural language
              └────────┬────────┘
                       │ AppNameExtracted
                       ▼
              ┌─────────────────┐
              │  GitHub Agent   │  ← creates inventory-api + inventory-api-gitops repos
              └────────┬────────┘
                       │ ReposCreated
                       ▼
              ┌─────────────────┐
              │ Template Engine │  ← Jinja2 renders Node.js stack into both repos
              └────────┬────────┘
                       │ ReposPopulated
                       ▼
              ┌─────────────────┐
              │  ArgoCD Agent   │  ← registers ArgoCD Application CRD
              └────────┬────────┘
                       │ ArgoCDAppCreated → GitOpsSynced → WorkloadHealthy
                       ▼
         http://inventory-api.cnoe.localtest.me  🎉
```

**7 domain events. Zero manual steps.**

---

## 📋 Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Docker** (24+) | KinD cluster runs inside Docker |
| **Python 3.8+** | AI agent runtime |
| **GitHub PAT** | Scopes: `repo`, `workflow` |
| **OpenRouter API key** | Free tier works; used for NLP name extraction |
| `kubectl`, `curl`, `git` | Standard CLI tools |

`make setup` will tell you what's missing. `make preflight` validates everything before the live demo.

---

## 🎯 Make Targets

```
make help         → self-documenting target reference
make setup        → download idpbuilder binary + create venv + install deps
make bootstrap    → idpbuilder create (KinD + ArgoCD + Tekton + Nginx)
make preflight    → 8 pre-demo checks (env, tools, cluster, ArgoCD, GitHub, templates)
make demo         → run the AI onboarding agent end-to-end
make test         → run unit + integration test suite (v1 agent, v2 agent, manifests)
make status       → cluster + ArgoCD app status snapshot
make clean        → destroy cluster + remove venv + reset binaries
```

---

## 🏗️ Architecture

### Two Agent Implementations

| | v1 Agent (`ai-onboarding-agent/agent.py`) | v2 Agent (`src/agent.py`) |
|--|--|--|
| **Style** | Procedural | OOP `OnboardingAgent` class |
| **Entry point** | `make demo` | Direct import |
| **Config** | 3 env vars | 5 env vars, configurable paths |
| **Purpose** | Live demo | Production reference |

Both implementations are intentionally preserved. See [ADR-0022](docs/adr/0022-agent-architecture-v1-vs-v2.md) for the rationale.

### Platform Stack

```
KinD (Kubernetes in Docker)
├── ArgoCD          → GitOps reconciliation (https://cnoe.localtest.me/argocd)
├── Tekton          → CI pipeline runtime
├── Nginx           → Ingress controller (*.cnoe.localtest.me)
└── CNOE ecosystem  → Cloud Native Operational Excellence baseline
```

### Stack Templates (`cnoe-stacks/`)

- **`nodejs-template/`** — Node.js app source (index.js, Dockerfile, k8s manifests)
- **`nodejs-gitops-template/`** — ArgoCD Application + Kustomize overlays

---

## 🔍 Verify a Deployment

After `make demo`:

```bash
# ArgoCD CLI
argocd app get <app-name>
argocd app wait <app-name> --health

# Kubernetes
kubectl get pods -n <app-name>

# Hit the endpoint
curl http://<app-name>.cnoe.localtest.me
```

ArgoCD dashboard: **https://cnoe.localtest.me/argocd**
- Username: `admin`
- Password: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d`

---

## 📁 Repository Structure

```
agentic-powered-golden-path-demo/
├── Makefile                     # ← start here: make help
├── scripts/
│   ├── setup.sh                 # platform-aware bootstrap (macOS/Linux, amd64/arm64)
│   └── preflight.sh             # 8 pre-demo validation checks
├── ai-onboarding-agent/
│   ├── agent.py                 # v1 demo agent (procedural)
│   └── test_agent.py            # v1 unit tests
├── src/
│   ├── agent.py                 # v2 production agent (OOP)
│   └── test_agent.py            # v2 unit tests
├── cnoe-stacks/
│   ├── nodejs-template/         # Node.js application source template
│   └── nodejs-gitops-template/  # ArgoCD + k8s manifests template
├── tests/
│   ├── golden_path_tests.py
│   └── test-integration-e2e.py
├── docs/
│   ├── adr/                     # 22 Architecture Decision Records (ADR-0001–0022)
│   └── ddd/                     # 13 Domain-Driven Design documents
├── requirements.txt
└── .github/workflows/ci.yml     # 5-job CI: lint, test-v1, test-v2, validate-manifests, smoke
```

---

## 📚 Decision Trail

This repo ships with complete architectural documentation:

- **22 ADRs** (`docs/adr/`) — every non-obvious decision recorded with context, alternatives, and consequences
- **13 DDD documents** (`docs/ddd/`) — bounded contexts, domain events, ubiquitous language, and the [implementation runbook](docs/ddd/13-implementation-runbook.md)

Key ADRs:
- [ADR-0021](docs/adr/0021-makefile-single-entrypoint.md) — Why Makefile over Taskfile / justfile / pyproject scripts
- [ADR-0022](docs/adr/0022-agent-architecture-v1-vs-v2.md) — v1 vs v2 agent co-existence strategy

---

## 🔧 Troubleshooting

**idpbuilder fails to start**
```bash
docker ps          # Docker must be running
make clean         # tear down any partial state
make bootstrap     # retry
```

**ArgoCD stuck / apps not syncing**
```bash
make status        # snapshot current state
kubectl get pods -n argocd
argocd app sync <app-name> --force
```

**GitHub push fails**
```bash
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
# Must return your user object — not a 401
```

**`openai` module not found / import errors**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

See [docs/ddd/13-implementation-runbook.md](docs/ddd/13-implementation-runbook.md) for the full troubleshooting guide.

---

## 🤝 Contributing

```bash
make test          # run full test suite before opening a PR
```

CI runs on every push: lint (ruff), test-v1, test-v2, manifest validation, dry-run smoke.

---

## 📄 License

Apache-2.0 — see [LICENSE](LICENSE).
