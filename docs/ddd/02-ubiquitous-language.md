# 02 — Ubiquitous Language

This glossary is the **single source of truth** for terminology in this project. Use these words in code identifiers, prompts, log messages, commit messages, ADRs, dashboards, and conversations. When a term in code or prose drifts from this list, fix the term — not the list — unless this list is wrong, in which case open a PR to update the list and everything downstream.

The glossary is grouped by bounded context for readability; cross-context terms are listed in *Cross-cutting* at the end.

---

## Onboarding (core)

| Term                          | Definition                                                                                                                                                |
|-------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Onboarding Request**        | A natural-language utterance from a Developer expressing intent to create a new service. Inbound to the agent; never persisted.                           |
| **Onboarding Workflow**       | The orchestrated sequence: extract → provision source → provision GitOps → register Argo Application → return.                                            |
| **Onboarding Run**            | A single execution of the Onboarding Workflow for one Onboarding Request. Has a unique correlation ID, a start/end timestamp, and an outcome.             |
| **Outcome**                   | The result of an Onboarding Run: `Succeeded`, `Failed`, `Cancelled`. Includes a structured reason on failure.                                              |
| **App Name**                  | A DNS-compatible slug (lowercase, hyphens, no leading/trailing dash, ≤ 63 chars). The unique identifier of an onboarded service across all contexts.       |
| **App Description**           | Free-text human description, used in `package.json`, `README.md`, and GitHub repo descriptions.                                                            |
| **Intent Extraction**         | The step that converts an Onboarding Request into a structured `(AppName, Stack, AppDescription)` tuple. Implemented by an LLM with regex fallback.        |

## Stack Catalog (supporting)

| Term                | Definition                                                                                                                       |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------|
| **Stack**           | A named opinionated runtime + framework choice (e.g. *NodeJS*). Composed of a Source Template and a GitOps Template.            |
| **Source Template** | The directory of files rendered into `<app>-source` (e.g. `cnoe-stacks/nodejs-template/app-source/`).                           |
| **GitOps Template** | The directory of files rendered into `<app>-gitops` (e.g. `cnoe-stacks/nodejs-gitops-template/`).                                |
| **Stack Manifest**  | The future `stack.yaml` describing a Stack's name, version, required variables, and template paths.                              |
| **Template Variable** | A Jinja2-rendered placeholder. Canonical variables: `appName`, `description`, `namespace`, `image`, `replicas`, `host`.        |
| **Render**          | The act of producing concrete files by substituting Template Variables into a Template.                                          |

## Source Code Provisioning (supporting)

| Term                            | Definition                                                                                                          |
|---------------------------------|---------------------------------------------------------------------------------------------------------------------|
| **Source Repository**           | The GitHub repository named `<AppName>-source`. Contains the application code rendered from the Source Template.    |
| **Source Repository URL**       | Canonical HTTPS clone URL of the Source Repository.                                                                  |
| **Initial Commit**              | The single first commit produced by the agent: *"Initial commit from Golden Path Agent"*.                            |

## GitOps Configuration (supporting)

| Term                         | Definition                                                                                                                                       |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| **GitOps Repository**        | The GitHub repository named `<AppName>-gitops`. Contains the Kubernetes manifests rendered from the GitOps Template.                              |
| **Desired State**            | The contents of the GitOps Repository at HEAD; the source of truth for what should be running.                                                    |
| **Manifest**                 | A single Kubernetes resource definition (YAML) inside the GitOps Repository — `Deployment`, `Service`, `Ingress`, etc.                            |
| **Promotion**                | A commit to the GitOps Repository that advances the Desired State (e.g. image bump, replica count, config change).                                |
| **Rollback**                 | A `git revert` on the GitOps Repository that returns the Desired State to a previous good commit (see ADR-0019).                                  |

## Deployment Orchestration (supporting)

| Term                       | Definition                                                                                                                                 |
|----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------|
| **Argo Application**       | An ArgoCD `Application` custom resource that points at a GitOps Repository and a target Namespace.                                          |
| **Sync**                   | An ArgoCD operation that applies the Desired State to the cluster. Can be automated, manual, or self-healing.                              |
| **Sync Status**            | One of `Synced`, `OutOfSync`. Reflects whether cluster state matches Desired State.                                                         |
| **Health Status**          | One of `Healthy`, `Progressing`, `Degraded`, `Suspended`, `Missing`, `Unknown`. Reflects workload readiness.                                |
| **Namespace**              | The Kubernetes namespace into which the Argo Application's Manifests land. By convention `<AppName>` (ADR-0017).                            |
| **Workload**               | The runtime objects (Pods, ReplicaSets) that materialise from a Deployment Manifest.                                                        |

## Observability (supporting)

| Term                  | Definition                                                                                                          |
|-----------------------|---------------------------------------------------------------------------------------------------------------------|
| **Telemetry**         | Metrics, logs, and traces emitted by an onboarded application.                                                       |
| **ServiceMonitor**    | The Prometheus-Operator CRD that registers an application's `/metrics` endpoint for scraping.                        |
| **OTLP Endpoint**     | The OpenTelemetry Collector endpoint to which app SDKs send traces and metrics.                                      |
| **Standard Dashboard**| The Grafana dashboard that every onboarded application inherits, keyed by `app=<AppName>`.                           |

---

## Cross-cutting

| Term                      | Definition                                                                                                                          |
|---------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| **Platform**              | The bundle of KinD + ArgoCD + Tekton + ingress + observability stack provisioned by idpbuilder. Pre-existent to any Onboarding Run. |
| **Correlation ID**        | A UUID generated at the start of an Onboarding Run; threaded through logs and Domain Events.                                        |
| **Domain Event**          | A past-tense fact emitted by an aggregate (`SourceRepositoryCreated`, `ArgoApplicationRegistered`, …). See doc 07.                   |
| **Tool**                  | One of the agent's three orchestrated capabilities: *Create GitHub Repo*, *Populate Repo From Stack*, *Create Argo Application*.    |
| **Golden Path**           | The opinionated, fully-automated route from intent to running service. Every Stack defines one Golden Path.                          |

## Anti-vocabulary (terms to avoid)

These words are common in the wider industry but **mean different things in different contexts** and so cause confusion here. Use the listed replacements.

| Avoid           | Use instead                                              | Why                                                           |
|-----------------|----------------------------------------------------------|---------------------------------------------------------------|
| **App**         | *Onboarded Application*, *Argo Application*, *App Name* | "App" is fatally ambiguous between user-app, ArgoCD App, slug |
| **Repo**        | *Source Repository* or *GitOps Repository*               | Always specify which                                          |
| **Deploy**      | *Sync* (ArgoCD), *Promotion* (Git commit), *Rollout* (k8s)| Each is a distinct concept                                    |
| **Service**     | *Onboarded Application* (in DDD prose), *Service* (k8s)  | Reserve unqualified "Service" for the k8s resource            |
| **Pipeline**    | *Onboarding Workflow* (ours), *Tekton Pipeline* (theirs) | Different scopes                                              |
| **Manifest**    | (allow when k8s YAML); else *Stack Manifest*             | Disambiguate                                                  |

## Discipline

When reviewing code or PRs:

1. If a new noun appears that isn't in this glossary, request that it be added (or an existing term reused).
2. If a term in code uses anti-vocabulary, request a rename.
3. If two PRs introduce two names for the same thing in different files, both reviewers must converge on a single term and update this document.
