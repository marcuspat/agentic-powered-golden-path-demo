# Use Case Guide

This guide explains who the Golden Path agent is for, what problems it solves,
and how different personas interact with it. Read this alongside the
[README](../README.md) (what it is) and the
[Validation Report](VALIDATION-REPORT.md) (evidence it works).

---

## What Problem Does This Solve?

When a developer joins an organisation or starts a new service, the typical
onboarding path looks like this:

1. Request a GitHub repository from the platform team (ticket, wait)
2. Copy-paste a template and manually replace all placeholder values
3. Create a second "GitOps" repo and wire it to ArgoCD (another ticket, wait)
4. Write Kubernetes manifests — namespace, network policy, resource quota,
   secrets wiring, monitoring hooks
5. Register the application in ArgoCD and wait for the first sync

This process is error-prone, slow (often days), and does not scale as the
number of teams grows.

The Golden Path agent replaces all of those steps with one command:

```bash
python -m agent onboard "I need to deploy my new NodeJS service called inventory-api"
```

The agent:
1. Extracts the application name from the natural-language request
2. Creates a source repository from a production-ready template
3. Creates a GitOps repository with Kubernetes manifests tailored to the app
4. Registers an ArgoCD `Application` that immediately begins reconciling
5. Emits structured events for audit and observability

The whole flow runs unattended, end-to-end, in a single invocation.

---

## Personas and Use Cases

### Platform Engineer

**You are building or maintaining the IDP.** You want to understand the
architecture, extend it with new stack templates, or adapt it for your
organisation's tooling choices.

**How the Golden Path helps you:**

- The layered `agent/` package (domain → application → infrastructure) makes
  it straightforward to swap any adapter — swap GitHub for GitLab, ArgoCD for
  Flux, or add a Slack notification adapter — without rewriting business logic.
- Stack templates live in `cnoe-stacks/` as Jinja2 directories. Adding a new
  language or framework stack is a matter of dropping in a new directory and
  registering it in the catalog adapter.
- The ADR collection (`docs/adr/`) documents every architectural choice and its
  trade-offs, so you can evaluate whether a decision still fits your context.
- The five-tier test suite (`make test-all`) gives you a safety net when
  modifying core logic.

**Key files to read first:**

| File | Why |
|---|---|
| `docs/adr/0013-monolithic-cli-agent-architecture.md` | Why the agent is a single CLI rather than a microservice |
| `docs/ddd/03-bounded-contexts.md` | Where the domain boundaries are |
| `agent/domain/ports.py` | Every external dependency is represented as a Protocol here |
| `agent/composition.py` | How all the adapters are wired together |
| `cnoe-stacks/nodejs-template/` | Example of a full stack template |

**Extending the stack catalog:**

```bash
# 1. Create a new stack directory
mkdir -p cnoe-stacks/python-fastapi-template/app-source
# 2. Add your Jinja2-templated files
# 3. Add a matching gitops template directory
mkdir -p cnoe-stacks/python-fastapi-gitops-template
# 4. Register the stack in the catalog adapter
#    See: agent/infrastructure/catalog/fs_repo.py
```

---

### Application Developer

**You are a developer who wants to spin up a new service quickly.** You do not
need to understand the internals — you just need the service to appear and be
deployable.

**How the Golden Path helps you:**

- One command, plain English. No tickets, no waiting for the platform team.
- The resulting repositories are fully production-ready: CI pipeline wired,
  Kubernetes manifests with resource limits and network policies, secrets
  managed via ExternalSecret (no plaintext credentials in git).
- If you make a mistake (wrong name, wrong template), `cleanup` reverses
  the provisioning:

```bash
python -m agent cleanup inventory-api --repos
```

**Typical day-one workflow:**

```bash
# Check that your environment is configured
python -m agent --validate-env

# Onboard a new service
python -m agent onboard "Deploy my checkout-service NodeJS application"

# Watch the ArgoCD dashboard for the first sync
# https://cnoe.localtest.me/argocd

# Your service is now live at:
# http://checkout-service.cnoe.localtest.me
```

**Iterating without live infrastructure:**

```bash
# Verify the agent parses your request correctly before committing to live calls
python -m agent onboard "Deploy my checkout-service" --dry-run --no-llm
```

---

### Platform / IDP Evaluator

**You are assessing whether this reference implementation is a good foundation
for your organisation's Golden Path.** You want to understand the quality of
the code, the completeness of the implementation, and what would need to change
to adapt it.

**What this repository demonstrates:**

| Capability | Evidence |
|---|---|
| Clean architecture | `agent/` follows hexagonal (ports-and-adapters) design; domain has no infrastructure imports |
| Test coverage | 156 unit + integration tests, 19 security tests, 11 perf benchmarks — all green |
| Security posture | No plaintext secrets in git; ExternalSecret CRs; credential scanner in CI |
| Dependency hygiene | `pip-audit` clean; pinned transitive CVE floors; documented ignores with justification |
| CI gate | GitHub Actions matrix on Python 3.9 + 3.12; lint + typecheck + test + security + secret scan |
| Observability | JSONL structured event emission; ServiceMonitor for Prometheus scraping |
| Decision audit trail | 20 ADRs document every significant architectural choice |
| Domain model | 12 DDD documents including bounded contexts, aggregates, and ubiquitous language |

**What would need to change for production:**

| Item | Notes |
|---|---|
| GitHub org | Templates hardcode `cnoe-io/` prefixes — adapt to your org |
| Secret store | ExternalSecret CRs reference a generic store — configure for Vault, AWS Secrets Manager, etc. |
| LLM provider | OpenRouter is the default; swap via the `IntentExtractorPort` |
| Domain name | `cnoe.localtest.me` is the local dev wildcard — replace with your cluster's ingress domain |
| E2E test gate | The Tier 3 suite (`tests/e2e/`) validates the full live flow; run it in a dedicated CI environment |

**Quickest way to evaluate end-to-end:**

```bash
# Stand up the local platform
./idpbuilder create

# Set credentials
export GITHUB_TOKEN=<token>
export GITHUB_USERNAME=<user>
export OPENROUTER_API_KEY=<key>

# Run the complete local demo
python -m agent onboard "Deploy my demo-service NodeJS application"

# Observe in ArgoCD
# https://cnoe.localtest.me/argocd
```

---

## Scenario Walkthroughs

### Scenario A: Onboard a new service (happy path)

```bash
# 1. Verify environment
$ python -m agent --validate-env
# (exits 0 — all vars present)

# 2. Onboard
$ python -m agent onboard "I need to deploy my inventory-api service"
# Agent extracts app name: inventory-api
# Creates: inventory-api-source (GitHub repo)
# Creates: inventory-api-gitops (GitHub repo)
# Pushes NodeJS template to source repo
# Pushes k8s manifests to gitops repo
# Creates ArgoCD Application: inventory-api
# Exit 0

# 3. Check ArgoCD
$ argocd app get inventory-api
# Status: Synced / Healthy

# 4. Access the service
# http://inventory-api.cnoe.localtest.me
```

### Scenario B: Validate parsing before provisioning

```bash
$ python -m agent onboard \
    "Create a payment-processor microservice for the checkout team" \
    --dry-run --no-llm

# Output shows extracted intent without creating anything:
# ⚠️  Onboarding cancelled
#    reason: dry_run
# Exit 2 (cancelled, not error)
```

### Scenario C: Undo a provisioned application

```bash
# Remove ArgoCD application and Kubernetes namespace;
# keep the GitHub repositories for audit purposes
$ python -m agent cleanup inventory-api

# Remove everything including GitHub repos
$ python -m agent cleanup inventory-api --repos
```

### Scenario D: Add a new stack template

```bash
# 1. Create the template directory structure
mkdir -p cnoe-stacks/python-fastapi-template/app-source
mkdir -p cnoe-stacks/python-fastapi-gitops-template

# 2. Populate with Jinja2-templated files
#    Use {{ app_name }}, {{ description }}, {{ namespace }} as variables
#    See cnoe-stacks/nodejs-template/ for reference

# 3. Register in the catalog adapter
#    Edit agent/infrastructure/catalog/fs_repo.py
#    Add an entry to the STACK_REGISTRY dict

# 4. Write integration tests
#    See tests/integration/test_template_rendering.py

# 5. Run the gate
make test-all
```

### Scenario E: Swap the VCS provider (GitLab example)

```bash
# 1. Implement the SourceRepoPort and GitOpsRepoPort protocols
#    See agent/domain/ports.py for the interface contracts

# 2. Create the adapter
mkdir -p agent/infrastructure/gitlab
touch agent/infrastructure/gitlab/adapter.py
# Implement: create_source_repo(), create_gitops_repo(), etc.

# 3. Wire the new adapter in composition.py
#    Replace the GitHub adapters with your GitLab adapters

# 4. No changes needed in domain/ or application/ layers
```

---

## Frequently Asked Questions

**Q: Does this require an internet connection to run?**

For the `--dry-run --no-llm` path: no. For live onboarding: yes — GitHub and
optionally OpenRouter are called.

**Q: What if I don't have an OpenRouter API key?**

Pass `--no-llm`. The agent falls back to a regex-based extractor that parses
quoted app names and common patterns ("service called X", "deploy X").

**Q: Can I run this without the KinD cluster?**

The dry-run path skips all external calls including Kubernetes. To run live
onboarding without a local cluster, point `KUBECONFIG` at an existing cluster
(staging, etc.) where ArgoCD is installed.

**Q: How do I run the full end-to-end tests?**

```bash
./idpbuilder create
export GITHUB_TOKEN=... GITHUB_USERNAME=... OPENROUTER_API_KEY=...
RUN_E2E=1 make test-e2e
```

Warning: this creates real GitHub repositories. The e2e tests clean up after
themselves, but verify your credentials have `delete_repo` scope.

**Q: Where are the ADRs and DDD documents?**

- Architecture Decision Records: [`docs/adr/`](adr/) (20 records)
- Domain-Driven Design: [`docs/ddd/`](ddd/) (12 documents)

**Q: Is there a pre-commit hook?**

Yes. After `pip install pre-commit && pre-commit install`, each commit runs
`ruff check` and the standalone secret scanner automatically.
