# ð Agentic Golden Path â AI-Powered Developer Onboarding

> **Say what you want to deploy. Watch it appear in ArgoCD.**

Natural language in â GitHub repos created â Kubernetes workload running â ArgoCD synced. Under 2 minutes, zero manual steps.

[![CI](https://github.com/marcuspat/agentic-powered-golden-path-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/marcuspat/agentic-powered-golden-path-demo/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

---

## â¡ Quick Start â Three Commands

```bash
git clone https://github.com/marcuspat/agentic-powered-golden-path-demo.git
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

## ðºï¸ How It Works

```
Developer: "I need to deploy my inventory-api service"
                        â
                        â¼
              âââââââââââââââââââ
              â  OpenRouter LLM  â  â extracts app name from natural language
              ââââââââââ¬âââââââââ
                       â AppNameExtracted
                       â¼
              âââââââââââââââââââ
              â  GitHub Agent   â  â creates inventory-api + inventory-api-gitops repos
              ââââââââââ¬âââââââââ
                       â ReposCreated
                       â¼
              âââââââââââââââââââ
              â Template Engine â  â Jinja2 renders Node.js stack into both repos
              ââââââââââ¬âââââââââ
                       â ReposPopulated
                       â¼
              âââââââââââââââââââ
              â  ArgoCD Agent   â  â registers ArgoCD Application CRD
              ââââââââââ¬âââââââââ
                       â ArgoCDAppCreated â GitOpsSynced â WorkloadHealthy
                       â¼
         http://inventory-api.cnoe.localtest.me  ð
```

**7 domain events. Zero manual steps.**

---

## ð Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Docker** (24+) | KinD cluster runs inside Docker |
| **Python 3.8+** | AI agent runtime |
| **GitHub PAT** | Scopes: `repo`, `workflow` |
| **OpenRouter API key** | Free tier works; used for NLP name extraction |
| `kubectl`, `curl`, `git` | Standard CLI tools |

`make setup` will tell you what's missing. `make preflight` validates everything before the live demo.

---

## ð¯ Make Targets

```
make help         â self-documenting target reference
make setup        â download idpbuilder binary + create venv + install deps
make bootstrap    â idpbuilder create (KinD + ArgoCD + Tekton + Nginx)
make preflight    â 8 pre-demo checks (env, tools, cluster, ArgoCD, GitHub, templates)
make demo         â run the AI onboarding agent end-to-end
make test         â run unit + integration test suite (v1 agent, v2 agent, manifests)
make status       â cluster + ArgoCD app status snapshot
make clean        â destroy cluster + remove venv + reset binaries
```

---

## ðï¸ Architecture

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
âââ ArgoCD          â GitOps reconciliation (https://cnoe.localtest.me/argocd)
âââ Tekton          â CI pipeline runtime
âââ Nginx           â Ingress controller (*.cnoe.localtest.me)
âââ CNOE ecosystem  â Cloud Native Operational Excellence baseline
```

### Stack Templates (`cnoe-stacks/`)

- **`nodejs-template/`** â Node.js app source (index.js, Dockerfile, k8s manifests)
- **`nodejs-gitops-template/`** â ArgoCD Application + Kustomize overlays

---

## ð Verify a Deployment

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

## ð Repository Structure

```
agentic-powered-golden-path-demo/
âââ Makefile                     # â start here: make help
âââ scripts/
â   âââ setup.sh                 # platform-aware bootstrap (macOS/Linux, amd64/arm64)
â   âââ preflight.sh             # 8 pre-demo validation checks
âââ ai-onboarding-agent/
â   âââ agent.py                 # v1 demo agent (procedural)
â   âââ test_agent.py            # v1 unit tests
âââ src/
â   âââ agent.py                 # v2 production agent (OOP)
â   âââ test_agent.py            # v2 unit tests
âââ cnoe-stacks/
â   âââ nodejs-template/         # Node.js application source template
â   âââ nodejs-gitops-template/  # ArgoCD + k8s manifests template
âââ tests/
â   âââ golden_path_tests.py
â   âââ test-integration-e2e.py
âââ docs/
â   âââ adr/                     # 22 Architecture Decision Records (ADR-0001â0022)
â   âââ ddd/                     # 13 Domain-Driven Design documents
âââ requirements.txt
âââ .github/workflows/ci.yml     # 5-job CI: lint, test-v1, test-v2, validate-manifests, smoke
```

---

## ð Decision Trail

This repo ships with complete architectural documentation:

- **22 ADRs** (`docs/adr/`) â every non-obvious decision recorded with context, alternatives, and consequences
- **13 DDD documents** (`docs/ddd/`) â bounded contexts, domain events, ubiquitous language, and the [implementation runbook](docs/ddd/13-implementation-runbook.md)

Key ADRs:
- [ADR-0021](docs/adr/0021-makefile-single-entrypoint.md) â Why Makefile over Taskfile / justfile / pyproject scripts
- [ADR-0022](docs/adr/0022-agent-architecture-v1-vs-v2.md) â v1 vs v2 agent co-existence strategy

---

## ð§ Troubleshooting

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
# Must return your user object â not a 401
```

**`openai` module not found / import errors**
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

See [docs/ddd/13-implementation-runbook.md](docs/ddd/13-implementation-runbook.md) for the full troubleshooting guide.

---

## ð¤ Contributing

```bash
make test          # run full test suite before opening a PR
```

CI runs on every push: lint (ruff), test-v1, test-v2, manifest validation, dry-run smoke.

---

## ð License

Apache-2.0 â see [LICENSE](LICENSE).
