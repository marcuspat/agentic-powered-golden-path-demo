# 13 â Implementation Runbook

> Practical, operable guide for getting the Golden Path platform running from a cold clone. This document maps directly onto the domain model in docs 01â12 â commands here correspond to bounded contexts, aggregates, and domain services described there.

## Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Docker | 20.x | https://docs.docker.com/get-docker/ |
| kubectl | 1.28+ | `brew install kubectl` or OS package |
| git | 2.x | pre-installed on most systems |
| Python | 3.8+ | `brew install python` or OS package |
| make | any | pre-installed on macOS/Linux |

GitHub PAT scopes required: `repo` (full), `workflow` (optional, for Actions triggers).

---

## Phase 0 â Clone and Setup (Generic Infrastructure Context)

```bash
git clone https://github.com/adventurewave-labs/agentic-powered-golden-path-demo
cd agentic-powered-golden-path-demo
make setup
```

`make setup` invokes `scripts/setup.sh` which:
1. Detects platform (darwin/linux, amd64/arm64)
2. Downloads the correct idpbuilder binary if not present
3. Creates a Python virtual environment at `.venv/`
4. Installs all Python dependencies
5. Prints missing env var warnings

---

## Phase 1 â Platform Bootstrap (Container Runtime + IDP Context)

```bash
make bootstrap
```

This runs `./idpbuilder create` which provisions:
- KinD cluster (`agentic-golden-path` namespace)
- ArgoCD (namespace: `argocd`, URL: `https://cnoe.localtest.me/argocd`)
- Tekton (namespace: `tekton-pipelines`)
- Gitea (in-cluster Git, optional)
- Nginx ingress controller

Takes 5â15 minutes on first run (image pulls). Subsequent runs: ~60 seconds.

**Verify:**
```bash
make status
# Or manually:
kubectl get pods -A
./idpbuilder get status
```

**ArgoCD credentials:**
```bash
# URL
https://cnoe.localtest.me/argocd

# Admin password (dynamically retrieved)
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d && echo
```

---

## Phase 2 â Environment Configuration (Identity & Access Context)

```bash
export GITHUB_TOKEN=ghp_your_token_here
export GITHUB_USERNAME=your_github_username
export OPENROUTER_API_KEY=sk-or-your_openrouter_key
```

Or copy the example and fill in:
```bash
cp ai-onboarding-agent/.env.example ai-onboarding-agent/.env
# Edit .env with your credentials
# Then: source ai-onboarding-agent/.env  (or use direnv)
```

**Validate configuration:**
```bash
make preflight
```

---

## Phase 3 â Run the Demo (Core Onboarding Domain)

```bash
make demo
```

This sequence exercises all five DDD subdomains in order:

| Step | Domain Event | Bounded Context |
|------|-------------|-----------------|
| 1. Natural language â app name | `AppNameExtracted` | LLM Inference (Generic) |
| 2. Create `{app}-source` GitHub repo | `SourceRepositoryCreated` | Source Code Provisioning |
| 3. Push NodeJS template into source repo | `SourceRepositoryPopulated` | Stack Catalog + Source Provisioning |
| 4. Create `{app}-gitops` GitHub repo | `GitOpsRepositoryCreated` | GitOps Configuration |
| 5. Push K8s manifests into gitops repo | `GitOpsRepositoryPopulated` | GitOps Configuration |
| 6. `kubectl apply` ArgoCD Application | `ArgoApplicationRegistered` | Deployment Orchestration |
| 7. ArgoCD reconciles â pods running | `WorkloadHealthy` | Deployment Orchestration |

**Expected output (truncated):**
```
[INFO] Extracting app info from: "I need to deploy my NodeJS service called inventory-api"
[INFO] ð¤ AI extracted app name: inventory-api
[INFO] Tool: Creating GitHub repo for inventory-api...
[INFO] Successfully created repos: ...inventory-api-source.git, ...inventory-api-gitops.git
[INFO] Tool: Populating .../inventory-api-source from .../nodejs-template/app-source...
[INFO] Tool: Populating .../inventory-api-gitops from .../nodejs-gitops-template...
[INFO] Tool: Creating ArgoCD Application for inventory-api...
[INFO] Successfully applied ArgoCD Application manifest.
[INFO] â Golden Path onboarding completed successfully!
[INFO] App will be available at: http://inventory-api.cnoe.localtest.me
```

---

## Phase 4 â Verify Deployment (Observability Context)

```bash
# Check ArgoCD shows application synced
argocd app get inventory-api

# Or via kubectl
kubectl get application inventory-api -n argocd

# Check pods in default namespace
kubectl get pods -n default

# Test the endpoint (after ~60s for sync)
curl http://inventory-api.cnoe.localtest.me
# Expected: "Hello from our Golden Path App!"
```

---

## Running Tests

```bash
make test
# Runs: pytest src/ ai-onboarding-agent/ -v --tb=short
```

CI runs these same tests in GitHub Actions on every push (5 jobs: lint, test-v1, test-v2, validate-manifests, dry-run-smoke).

---

## Teardown

```bash
make clean
# Runs: ./idpbuilder delete
```

This removes the KinD cluster and all resources. GitHub repos created during the demo remain â delete them manually via `gh repo delete` or the GitHub UI.

---

## Troubleshooting

### idpbuilder fails to start

```bash
# Check Docker is running
docker info

# Check port 443 isn't in use (idpbuilder needs it for ingress)
lsof -i :443

# Check available memory (KinD needs ~4GB)
docker stats --no-stream
```

### ArgoCD app stuck in "Unknown" state

```bash
# Force sync
argocd app sync inventory-api --force

# Check repo is accessible from within cluster
argocd app get inventory-api
# Look for "ComparisonError" â usually means gitops repo URL is wrong
```

### GitHub push fails during `populate_repo_from_stack`

```bash
# Verify token has repo scope
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | jq .login

# Ensure git credential helper uses the token
git config --global credential.helper store
echo "https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com" >> ~/.git-credentials
```

### Python `openai` module not found

```bash
# Agent falls back to regex extraction â this is expected behaviour.
# To enable full AI extraction:
pip install openai  # or: pip install -r ai-onboarding-agent/requirements.txt
```

### Templates not rendering `{{appName}}`

Jinja2 uses `{{ appName }}` (with spaces) by default but also accepts `{{appName}}`.
If you see literal `{{appName}}` in committed files, check that `Template(content).render(appName=...)` 
is being called, not just string formatting.

---

## Make Target Reference

| Target | Description |
|--------|-------------|
| `make help` | List all targets with descriptions |
| `make setup` | Install deps, download idpbuilder, check prereqs |
| `make bootstrap` | Create KinD cluster with ArgoCD via idpbuilder |
| `make preflight` | Validate env vars and cluster readiness |
| `make demo` | Run full end-to-end demo |
| `make test` | Run pytest test suite |
| `make status` | Show cluster and ArgoCD status |
| `make clean` | Tear down KinD cluster |

---

## Domain Event Log Format

Every significant step emits a structured log line:

```
2026-06-16 12:34:56 - INFO - Tool: Creating GitHub repo for inventory-api...
2026-06-16 12:34:58 - INFO - Successfully created repos: ...
```

Future: these will be published as structured JSON to an event bus so downstream systems (Slack notifications, audit pipelines, billing) can subscribe. See `docs/ddd/07-domain-events.md` for the full event catalogue.
