# 03 — Bounded Contexts

A **Bounded Context** is the scope within which a particular model — its terms, rules, and consistency boundaries — applies without contradiction. Each subdomain identified in [`01-domain-overview.md`](./01-domain-overview.md) maps to one bounded context. Within a context the language is unambiguous; at context boundaries we translate (see [`11-anti-corruption-layers.md`](./11-anti-corruption-layers.md)).

This document enumerates each bounded context with: purpose, responsibilities, internal vocabulary, key aggregates, integration points, and ownership.

---

## BC-1 — Onboarding (Core)

| Attribute       | Detail                                                                                            |
|-----------------|---------------------------------------------------------------------------------------------------|
| **Purpose**     | Translate Developer intent into a coordinated invocation of all supporting contexts.              |
| **Owner**       | Agent Engineering                                                                                  |
| **Code home**   | `ai-onboarding-agent/agent.py` (`run_onboarding_flow`, `extract_app_name_from_request`)           |
| **Aggregates**  | `OnboardingRun`                                                                                    |
| **Value Objects** | `AppName`, `OnboardingRequest`, `Outcome`, `CorrelationId`                                       |
| **Domain Services** | `IntentExtractionService`                                                                       |
| **Events Published** | `OnboardingRunStarted`, `OnboardingRunCompleted`, `OnboardingRunFailed`                       |
| **Events Consumed** | `SourceRepositoryCreated`, `GitOpsRepositoryPopulated`, `ArgoApplicationRegistered`             |
| **Related ADRs** | [0004](../adr/0004-use-python-for-onboarding-agent.md), [0005](../adr/0005-use-openrouter-as-llm-gateway.md), [0011](../adr/0011-pattern-matching-fallback.md), [0013](../adr/0013-monolithic-cli-agent-architecture.md) |

**Internal vocabulary** — see *Onboarding* in [`02-ubiquitous-language.md`](./02-ubiquitous-language.md).

**Boundaries** — Onboarding is the **upstream initiator**. It calls into all other contexts but is called by none of them (other than at start-up by the CLI entry point).

---

## BC-2 — Stack Catalog

| Attribute       | Detail                                                                                                              |
|-----------------|---------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Define and serve the opinionated golden-path templates available for onboarding.                                    |
| **Owner**       | Platform Engineering                                                                                                 |
| **Code home**   | `cnoe-stacks/` (canonical), `templates/` (deprecated copy slated for removal — ADR-0012)                            |
| **Aggregates**  | `Stack` (composite of `SourceTemplate` + `GitOpsTemplate` + future `StackManifest`)                                 |
| **Value Objects** | `StackName`, `StackVersion`, `TemplatePath`, `TemplateVariableSet`                                                 |
| **Domain Services** | `TemplateRenderingService` (Jinja2 render with sanitisation)                                                     |
| **Events Published** | `StackRendered`                                                                                                  |
| **Events Consumed** | (none — read-only catalog)                                                                                        |
| **Related ADRs** | [0007](../adr/0007-use-jinja2-for-template-rendering.md), [0012](../adr/0012-use-cnoe-stacks-for-templates.md)      |

**Boundaries** — pure read model from the agent's perspective. New stacks are added via PR to this repository, not at runtime.

---

## BC-3 — Source Code Provisioning

| Attribute       | Detail                                                                                                                  |
|-----------------|-------------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Materialise a `<AppName>-source` GitHub repository populated from a Source Template.                                    |
| **Owner**       | Platform Engineering                                                                                                     |
| **Code home**   | `agent.py:create_github_repo()`, `agent.py:populate_repo_from_stack()` (when invoked with the source template path)     |
| **Aggregates**  | `SourceRepository`                                                                                                       |
| **Value Objects** | `RepositoryUrl`, `CommitMessage`, `BranchName`                                                                          |
| **Domain Services** | `GitHubRepositoryService`, `GitWorkingCopyService`                                                                    |
| **Events Published** | `SourceRepositoryCreated`, `SourceRepositoryPopulated`                                                              |
| **Events Consumed** | `OnboardingRunStarted`                                                                                                |
| **Related ADRs** | [0006](../adr/0006-two-repository-pattern.md), [0008](../adr/0008-use-github-as-vcs-provider.md)                        |

---

## BC-4 — GitOps Configuration

| Attribute       | Detail                                                                                                                  |
|-----------------|-------------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Materialise a `<AppName>-gitops` GitHub repository populated from a GitOps Template, defining Desired State.            |
| **Owner**       | Platform Engineering                                                                                                     |
| **Code home**   | `agent.py:create_github_repo()` and `agent.py:populate_repo_from_stack()` (with the GitOps template path)               |
| **Aggregates**  | `GitOpsRepository`                                                                                                       |
| **Value Objects** | `RepositoryUrl`, `Manifest`, `KustomizationPath`, `Namespace`                                                         |
| **Domain Services** | `GitHubRepositoryService`, `GitWorkingCopyService` (shared with BC-3)                                                  |
| **Events Published** | `GitOpsRepositoryCreated`, `GitOpsRepositoryPopulated`                                                              |
| **Events Consumed** | `OnboardingRunStarted`                                                                                                |
| **Related ADRs** | [0006](../adr/0006-two-repository-pattern.md), [0017](../adr/0017-namespace-isolation-strategy.md), [0018](../adr/0018-credential-management-approach.md), [0019](../adr/0019-rollback-strategy.md) |

**Note** — BC-3 and BC-4 share infrastructure (`GitHubRepositoryService`, `GitWorkingCopyService`) but model different invariants (Source Repository never contains Kubernetes manifests; GitOps Repository never contains application source code beyond image references). They are kept as **separate contexts** to preserve those invariants and to allow distinct ownership and review processes.

---

## BC-5 — Deployment Orchestration

| Attribute       | Detail                                                                                                                |
|-----------------|-----------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Translate GitOps Desired State into a running Workload by registering an Argo Application.                            |
| **Owner**       | Platform Engineering                                                                                                   |
| **Code home**   | `agent.py:create_argocd_application()`                                                                                 |
| **Aggregates**  | `ArgoApplication`                                                                                                      |
| **Value Objects** | `Namespace`, `SyncPolicy`, `SyncStatus`, `HealthStatus`                                                              |
| **Domain Services** | `KubernetesApplyService`                                                                                            |
| **Events Published** | `ArgoApplicationRegistered`, `ArgoApplicationSyncStarted`, `ArgoApplicationSynced`, `WorkloadHealthy`             |
| **Events Consumed** | `GitOpsRepositoryPopulated`                                                                                         |
| **Related ADRs** | [0003](../adr/0003-adopt-argocd-for-gitops-deployment.md), [0017](../adr/0017-namespace-isolation-strategy.md)         |

**Boundaries** — the agent is involved only at **registration**. Subsequent sync and health events are emitted by ArgoCD itself and observed externally.

---

## BC-6 — Platform Provisioning

| Attribute       | Detail                                                                                                                          |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Bring up the underlying KinD cluster, ArgoCD, Tekton, ingress, and observability stack. Run **before** any Onboarding occurs.  |
| **Owner**       | Platform Engineering                                                                                                             |
| **Code home**   | `idpbuilder` binary (vendored), `idpbuilder-source/`, `boot.sh`, `scripts/deploy-demo.sh`                                       |
| **Aggregates**  | `Cluster` (treated as opaque outside this context)                                                                              |
| **Value Objects** | `ClusterName`, `KubeConfigPath`                                                                                                |
| **Domain Services** | `IdpBuilderService`                                                                                                          |
| **Events Published** | `ClusterReady`, `PlatformReady`                                                                                              |
| **Events Consumed** | (none)                                                                                                                       |
| **Related ADRs** | [0002](../adr/0002-use-idpbuilder-for-platform-bootstrap.md), [0009](../adr/0009-use-kind-for-local-kubernetes.md), [0010](../adr/0010-use-tekton-for-ci-pipelines.md), [0016](../adr/0016-localtest-me-for-local-dns.md) |

---

## BC-7 — Observability

| Attribute       | Detail                                                                                                                  |
|-----------------|-------------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Wire telemetry into every onboarded application by augmenting Stack Templates and the cluster monitoring stack.         |
| **Owner**       | SRE                                                                                                                      |
| **Code home**   | `config/monitoring/`, additions to `cnoe-stacks/nodejs-template/` and `cnoe-stacks/nodejs-gitops-template/` (planned)    |
| **Aggregates**  | `ObservabilityProfile`                                                                                                   |
| **Value Objects** | `MetricsEndpoint`, `OtlpEndpoint`, `DashboardUid`                                                                       |
| **Domain Services** | `DashboardProvisioningService`                                                                                        |
| **Events Published** | `WorkloadObserved`                                                                                                  |
| **Events Consumed** | `WorkloadHealthy`                                                                                                     |
| **Related ADRs** | [0020](../adr/0020-observability-strategy.md)                                                                            |

---

## BC-8 — Continuous Integration (Tekton)

| Attribute       | Detail                                                                                                                  |
|-----------------|-------------------------------------------------------------------------------------------------------------------------|
| **Purpose**     | Build, test, sign, and push container images for an Onboarded Application; commit image bumps back to the GitOps repo. |
| **Owner**       | Platform Engineering                                                                                                     |
| **Code home**   | (planned) `cnoe-stacks/nodejs-template/.tekton/`                                                                        |
| **Aggregates**  | `PipelineRun`                                                                                                            |
| **Value Objects** | `ImageTag`, `BuildResult`                                                                                              |
| **Events Published** | `ImageBuilt`, `GitOpsImageBumped`                                                                                   |
| **Events Consumed** | `SourceRepositoryPopulated` (initial), `SourceRepositoryUpdated` (subsequent commits)                                 |
| **Related ADRs** | [0010](../adr/0010-use-tekton-for-ci-pipelines.md)                                                                       |

**Status** — not yet implemented. Documented here as the target.

---

## Context summary

```
                                              ┌────────────────────────┐
                                              │  BC-6  Platform        │
                                              │  Provisioning          │
                                              │  (idpbuilder)          │
                                              └───────────┬────────────┘
                                                          │ provides cluster
                                                          ▼
┌─────────────────┐  uses    ┌────────────────────────────────────────────┐
│  BC-2  Stack    │◄─────────┤  BC-1  Onboarding (Core)                   │
│  Catalog        │          └─────┬───────────────┬──────────────┬───────┘
└─────────────────┘                │               │              │
                                   ▼               ▼              ▼
                           ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
                           │  BC-3 Source │ │  BC-4 GitOps │ │  BC-5 Deployment │
                           │  Provisioning│ │  Config      │ │  Orchestration   │
                           └──────┬───────┘ └──────┬───────┘ └──────┬───────────┘
                                  │ source code   │ desired state  │ argo apps
                                  ▼               ▼                ▼
                        ┌───────────────┐ ┌───────────────┐ ┌─────────────────┐
                        │  BC-8 Tekton  │ │ ArgoCD reads  │ │ Workloads run   │
                        │  CI (planned) │ │ from BC-4     │ │ in cluster      │
                        └───────────────┘ └───────────────┘ └────────┬────────┘
                                                                     │
                                                                     ▼
                                                           ┌─────────────────┐
                                                           │  BC-7           │
                                                           │  Observability  │
                                                           └─────────────────┘
```

A richer Mermaid diagram lives in [`./diagrams/context-map.md`](./diagrams/context-map.md).
