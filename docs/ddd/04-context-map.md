# 04 — Context Map

Where [`03-bounded-contexts.md`](./03-bounded-contexts.md) lists each bounded context, this document describes the **relationships between them** using DDD's standard integration patterns. The relationships are what make the system function as a whole, and they are what most often go wrong when a context's model leaks into a neighbour.

## Pattern legend

| Pattern                    | Symbol | Meaning                                                                                            |
|----------------------------|--------|----------------------------------------------------------------------------------------------------|
| **Customer / Supplier**    | `C/S`  | Upstream supplier serves downstream customer; customer's needs influence supplier's roadmap.       |
| **Conformist**             | `CF`   | Downstream conforms to upstream's model with no translation. Cheap, but couples deeply.            |
| **Anti-Corruption Layer**  | `ACL`  | Downstream wraps a foreign model in a local one to protect its language and rules.                 |
| **Open Host Service**      | `OHS`  | Upstream publishes a stable, public protocol for many downstream consumers.                        |
| **Published Language**     | `PL`   | A shared, documented format used between two contexts (often paired with OHS).                     |
| **Shared Kernel**          | `SK`   | A small chunk of model deliberately shared (and co-owned) between two contexts.                    |
| **Partnership**            | `P`    | Two contexts succeed or fail together; their teams co-design.                                      |
| **Separate Ways**          | `SW`   | No integration; intentional disconnect.                                                            |

## The map

```
                                       ┌──────────────────────────┐
                                       │  External: GitHub API    │
                                       └──────────┬───────────────┘
                                            OHS / ACL
                                                  │
              ┌──────────────────┐    P     ┌─────▼──────────────┐    C/S    ┌──────────────────┐
              │  BC-2 Stack      │◄────────►│  BC-1 Onboarding   │──────────►│ External:        │
              │  Catalog         │   (read) │  (Core)            │  ACL via  │ OpenRouter LLM   │
              └────────┬─────────┘          └─────┬──────────────┘           └──────────────────┘
                       │                          │ orchestrates
                       │ Stack templates          │
                       ▼                          ▼
              ┌──────────────────────────────────────────────┐
              │ BC-3 Source Provisioning      BC-4 GitOps    │
              │      (CF on Stack Catalog)         Config    │
              │                                (CF on Stack) │
              └────────────┬─────────────────────────┬───────┘
                           │                         │ desired state
                           │ source code             ▼
                           │                  ┌──────────────────┐  ACL  ┌──────────────────┐
                           │                  │ BC-5 Deployment  │──────►│ External: ArgoCD │
                           │                  │ Orchestration    │       │ + Kubernetes API │
                           │                  └────────┬─────────┘       └──────────────────┘
                           │                           │
                           ▼                           ▼ workloads run
                  ┌────────────────────┐      ┌────────────────────┐
                  │ BC-8 CI (Tekton)   │ C/S  │ BC-7 Observability │
                  │ (planned)          │─────►│                    │
                  └────────────────────┘      └────────────────────┘
                                                       ▲
                                              C/S      │ depends on
                                                       │
                                              ┌────────┴───────────┐
                                              │ BC-6 Platform      │
                                              │ Provisioning       │
                                              │ (idpbuilder)       │
                                              └────────────────────┘
```

## Relationships in detail

### Onboarding (BC-1) → GitHub API
- **Pattern:** Customer / Supplier with **Anti-Corruption Layer**.
- **Mechanism:** `GitHubRepositoryService` (a domain service in BC-3/BC-4) wraps `PyGithub` calls. Returns domain types (`SourceRepository`, `RepositoryUrl`) — never raw `Repository` objects from PyGithub leak into the agent's orchestration code.
- **Rationale:** insulates the agent from API changes (rate limits, deprecations, alternative providers — see ADR-0008). Allows substitution with Gitea or GitLab via a different adapter.

### Onboarding (BC-1) → OpenRouter LLM
- **Pattern:** Customer / Supplier with **Anti-Corruption Layer** *and* **fail-soft fallback**.
- **Mechanism:** `IntentExtractionService` calls OpenRouter, sanitises the output, and on any failure falls through to regex (ADR-0011). Domain code receives a clean `(AppName, …)` tuple, never an OpenAI `ChatCompletion` object.
- **Rationale:** Protects the core domain from LLM availability and prompt-engineering churn.

### Onboarding (BC-1) ↔ Stack Catalog (BC-2)
- **Pattern:** **Partnership** (read-side); BC-2 is also a **Published Language** (the Stack Manifest format) once `stack.yaml` exists.
- **Mechanism:** BC-1 reads templates and metadata from BC-2. BC-2 changes its template variables only with BC-1's coordination because BC-1 produces the variable bag.
- **Rationale:** the two contexts succeed or fail together; partnership avoids one trying to evolve faster than the other.

### Onboarding (BC-1) → Source Provisioning (BC-3) and GitOps Configuration (BC-4)
- **Pattern:** **Customer / Supplier**. BC-1 calls into BC-3 and BC-4 as services.
- **Mechanism:** Today these are function calls (`create_github_repo`, `populate_repo_from_stack`). Tomorrow they may be in-process service objects.

### BC-3 ↔ BC-4
- **Pattern:** **Shared Kernel** — both contexts use the same `GitHubRepositoryService` and `GitWorkingCopyService` infrastructure.
- **Mechanism:** the shared kernel is small (the two services and the `RepositoryUrl` value object). Domain models stay separate; e.g. `SourceRepository` and `GitOpsRepository` are distinct aggregates with distinct invariants (ADR-0006).

### BC-3 / BC-4 → Stack Catalog (BC-2)
- **Pattern:** **Conformist**.
- **Mechanism:** the provisioning contexts consume whatever shape BC-2 publishes; they do not translate. If BC-2 changes the variable name `appName` to `app_name`, BC-3 and BC-4 must change too.
- **Rationale:** conformist is acceptable because BC-2 is owned by the same team and changes go through the same review.

### BC-4 → Deployment Orchestration (BC-5)
- **Pattern:** **Customer / Supplier** via the GitOps Repository.
- **Mechanism:** BC-4 hands BC-5 a `RepositoryUrl`. BC-5 generates an `ArgoApplication` referencing that URL. BC-5 does *not* reach into BC-4's repository contents; it trusts that whatever lives at HEAD is valid Desired State.

### Deployment Orchestration (BC-5) → ArgoCD + Kubernetes
- **Pattern:** **Customer / Supplier with Anti-Corruption Layer**.
- **Mechanism:** `KubernetesApplyService` wraps `kubectl apply` (and the `kubernetes` Python client). Domain code never builds a `client.V1Deployment` directly; it constructs a domain `ArgoApplication` and the ACL serialises it to YAML.
- **Rationale:** insulates the domain from Kubernetes API churn and lets us swap to a different reconciler in the future (Flux, Spinnaker) by replacing the ACL.

### BC-5 → BC-7 Observability
- **Pattern:** **Customer / Supplier** (read-only).
- **Mechanism:** Observability does not influence Deployment Orchestration's model; it consumes the `WorkloadHealthy` event and surfaces it in dashboards.

### BC-6 Platform Provisioning → all
- **Pattern:** **Conformist** for everyone downstream.
- **Mechanism:** every other context assumes the cluster, ArgoCD, Tekton, ingress, and observability stack already exist. No translation; downstream contexts simply use the cluster.
- **Rationale:** the platform is a precondition, not a runtime dependency. It runs once at start-up.

### BC-8 CI (Tekton) → BC-4 GitOps Configuration
- **Pattern:** **Customer / Supplier** via Git commits (image bumps).
- **Mechanism:** BC-8's pipeline commits to `<app>-gitops` to update an image tag. BC-4 doesn't know or care that BC-8 made the commit; ArgoCD picks it up.

### BC-8 CI (Tekton) → BC-3 Source Provisioning
- **Pattern:** **Customer / Supplier** via webhooks (push events).
- **Mechanism:** BC-8 subscribes to GitHub webhooks on `<app>-source` to trigger pipelines.

## Trust and translation rules

The map encodes a few invariants that *must* hold:

1. **No raw external types in the core.** `PyGithub.Repository`, `openai.ChatCompletion`, `kubernetes.V1Deployment` etc. **must not** appear in `agent.py`'s orchestration code or in BC-1's domain types. ACLs translate them.
2. **GitOps Repository contents are sacred.** Only BC-4 (or BC-8 in its narrow scope of image bumps) commits to `<app>-gitops`. BC-5 reads via ArgoCD; it never pushes.
3. **App Name is the cross-context join key.** Every aggregate, event, and external reference uses the same `AppName` value object. No re-derivation, no parsing, no aliasing.
4. **Events flow forward.** BC-1 emits an `OnboardingRunStarted`; subsequent contexts emit their own events as they finish their work; BC-1 emits the terminal `OnboardingRunCompleted` only after observing all expected events. There are no back-edges in the event graph.

## Where these patterns appear in code

| Pattern instance                    | Today                                                                 | Target                                                          |
|-------------------------------------|-----------------------------------------------------------------------|-----------------------------------------------------------------|
| ACL around GitHub                   | inline in `create_github_repo()`                                      | Move into `agent/adapters/github_adapter.py`                    |
| ACL around OpenRouter               | inline in `extract_app_name_from_request()`                           | Move into `agent/adapters/openrouter_adapter.py`                 |
| ACL around kubectl                  | `subprocess.run(["kubectl", "apply", "-f", manifest])`                | `agent/adapters/kubernetes_adapter.py` with typed inputs         |
| Shared Kernel (BC-3/BC-4)           | `populate_repo_from_stack()` is reused                                | Extract `GitWorkingCopyService` and `GitHubRepositoryService`   |
| Partnership (BC-1/BC-2)             | implicit in stack template paths                                      | `stack.yaml` schema as Published Language                        |

See [`12-implementation-guide.md`](./12-implementation-guide.md) for the migration sequence.
