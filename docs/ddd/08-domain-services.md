# 08 — Domain Services

A **Domain Service** encapsulates domain logic that doesn't belong on a single aggregate or value object — typically because it coordinates multiple aggregates, performs domain-significant computation that depends on external state, or implements a stateless rule.

Domain Services live in the **domain layer**, alongside aggregates and value objects. They are pure interfaces from the application's perspective; their implementations may use *infrastructure* (HTTP clients, subprocess, file I/O), but those calls happen behind an interface.

This document specifies each service with its bounded context, signature, behaviour, side effects, and current implementation status.

## Service catalogue

| Service                                | Bounded Context                        | Status     |
|----------------------------------------|----------------------------------------|------------|
| `IntentExtractionService`              | BC-1 Onboarding                        | Implemented (inline in `agent.py`) |
| `OnboardingOrchestrationService`       | BC-1 Onboarding                        | Implemented (inline as `run_onboarding_flow`) |
| `TemplateRenderingService`             | BC-2 Stack Catalog                     | Implemented (inline in `populate_repo_from_stack`) |
| `StackSelectionService`                | BC-2 Stack Catalog                     | Planned (currently hard-coded) |
| `GitHubRepositoryService`              | BC-3, BC-4 (shared kernel)             | Implemented (inline) |
| `GitWorkingCopyService`                | BC-3, BC-4 (shared kernel)             | Implemented (inline) |
| `KubernetesApplyService`               | BC-5 Deployment Orchestration          | Implemented (inline) |
| `ArgoApplicationProjectionService`     | BC-5 Deployment Orchestration          | Planned    |
| `DashboardProvisioningService`         | BC-7 Observability                     | Planned    |
| `IdpBuilderService`                    | BC-6 Platform Provisioning             | External (uses `./idpbuilder` binary) |

---

## `IntentExtractionService`

**Purpose.** Convert an `OnboardingRequest` into a structured intent: `(AppName, StackName, AppDescription)`.

**Signature.**

```python
class IntentExtractionService(Protocol):
    def extract(self, request: OnboardingRequest) -> ExtractedIntent: ...

@dataclass(frozen=True)
class ExtractedIntent:
    app_name: AppName
    stack: StackName
    description: AppDescription
    extraction_path: ExtractionPath  # LLM | REGEX | DEFAULT
```

**Behaviour.**

1. Try the LLM (`OpenRouterAdapter`).
2. Validate and normalise the response into `AppName.from_raw(...)`.
3. On any exception or empty result, fall through to regex (ADR-0011).
4. On regex miss, fall through to `AppName.from_raw("my-app")` and stack=`StackName("nodejs")`.

**Side effects.** External HTTP call to OpenRouter. No state mutation; idempotent.

**Domain rules enforced.**

- Output `AppName` is always valid by construction.
- Output `StackName` references an existing `Stack` in the catalog (validated by caller).

**Implementation status.** Logic is in `agent.py:133`. The migration target moves it to `agent/domain/services/intent_extraction.py` with the LLM and regex paths as injectable strategies.

---

## `OnboardingOrchestrationService`

**Purpose.** Execute an `OnboardingRun` end-to-end. The "conductor" of the system.

**Signature.**

```python
class OnboardingOrchestrationService(Protocol):
    def run(self, request: OnboardingRequest) -> OnboardingRun: ...
```

**Behaviour.** Implements the workflow described in the [Domain Overview](./01-domain-overview.md):

1. Generate `CorrelationId`.
2. Create `OnboardingRun` aggregate; emit `OnboardingRun.Started`.
3. Call `IntentExtractionService`; emit `OnboardingRun.IntentExtracted`.
4. Look up `Stack` from the catalog (via `StackSelectionService`).
5. Call `SourceRepositoryProvisioner`; await `SourceRepository.Populated`.
6. Call `GitOpsRepositoryProvisioner`; await `GitOpsRepository.Populated`.
7. Call `ArgoApplicationRegistrar`; await `ArgoApplication.Registered`.
8. Mark `OnboardingRun` complete; emit `OnboardingRun.Completed`.
9. On any failure, mark the run failed and emit `OnboardingRun.Failed`. The current implementation does not roll back partial work; rollback semantics are documented in the *Implementation Guide* (doc 12) under "Compensating actions".

**Side effects.** Coordinates external systems via injected services; emits domain events; mutates the `OnboardingRun` aggregate.

---

## `TemplateRenderingService`

**Purpose.** Render a `Stack`'s templates into concrete files for a given variable bag.

**Signature.**

```python
class TemplateRenderingService(Protocol):
    def render(
        self,
        template: SourceTemplate | GitOpsTemplate,
        variables: TemplateVariables,
    ) -> List[RenderedFile]: ...
```

**Behaviour.**

- Walks the template directory.
- For each file, applies Jinja2 substitution with the variable bag.
- Returns a list of `(relative_path, bytes)` rather than writing to disk; the caller (a repository provisioner) decides where the bytes land.

**Domain rules.**

- Variables not declared in `Stack.declaredVariables` raise a domain error.
- Required variables missing from the bag raise a domain error.
- Identity render preserves files with no template syntax.

**Implementation status.** Inline in `populate_repo_from_stack()`; target location `agent/domain/services/template_rendering.py`.

---

## `StackSelectionService` (planned)

**Purpose.** Given an `ExtractedIntent`, return the appropriate `Stack` from the catalog.

**Signature.**

```python
class StackSelectionService(Protocol):
    def select(self, intent: ExtractedIntent) -> Stack: ...
```

**Behaviour.** Today the only stack is *nodejs* and selection is implicit. As the catalog grows the service will:

1. Look up `intent.stack` by name.
2. If multiple versions exist, choose the latest stable.
3. If none match, raise `StackNotFound`.

---

## `GitHubRepositoryService`

**Purpose.** Create and look up GitHub repositories. Shared by BC-3 and BC-4.

**Signature.**

```python
class GitHubRepositoryService(Protocol):
    def create(self, name: str, description: str, private: bool = False) -> RepositoryUrl: ...
    def exists(self, owner: str, name: str) -> bool: ...
```

**Behaviour.**

- Wraps the GitHub REST API (currently via `PyGithub`).
- On 422 *Repository already exists*, returns the canonical URL rather than failing — supports demo idempotency.
- All other errors propagate as domain exceptions: `RepositoryQuotaExceeded`, `Unauthorized`, `RateLimited`.

**Side effects.** External HTTP call. Creates a real GitHub repository (non-reversible from the agent's side; cleanup is manual).

---

## `GitWorkingCopyService`

**Purpose.** Manage local Git working copies to push initial commits. Shared by BC-3 and BC-4.

**Signature.**

```python
class GitWorkingCopyService(Protocol):
    def clone(self, url: RepositoryUrl, into: Path) -> WorkingCopy: ...
    def commit_all(self, copy: WorkingCopy, message: CommitMessage) -> GitSha: ...
    def push(self, copy: WorkingCopy, branch: BranchName = BranchName("main")) -> None: ...
```

**Behaviour.**

- Clones to a temp directory under `/tmp/<repo-name>`.
- Stages and commits all files in the working copy.
- Pushes to origin, retrying on transient network errors.

**Side effects.** Spawns `git` subprocess. Creates and removes a temp directory. Mutates a remote.

---

## `KubernetesApplyService`

**Purpose.** Apply Kubernetes manifests to the cluster. Used by BC-5 to register the `Application` CR.

**Signature.**

```python
class KubernetesApplyService(Protocol):
    def apply(self, manifest_yaml: str, *, namespace: Namespace | None = None) -> None: ...
```

**Behaviour.**

- Wraps `kubectl apply -f -` (preferred) or `kubernetes.utils.create_from_yaml` (where typed objects are needed).
- Idempotent on re-apply.
- Errors propagate as `K8sApplyError` with the underlying message preserved.

**Side effects.** Mutates the cluster.

---

## `ArgoApplicationProjectionService` (planned)

**Purpose.** Read the live state of an `ArgoApplication` from the cluster and project it into the domain `ArgoApplication` aggregate (`syncStatus`, `healthStatus`).

**Signature.**

```python
class ArgoApplicationProjectionService(Protocol):
    def get(self, name: AppName) -> ArgoApplication: ...
```

**Behaviour.** Reads the `Application` CR, translates ArgoCD's status fields into our `SyncStatus` / `HealthStatus` enums (translation lives in the ACL).

---

## `DashboardProvisioningService` (planned)

**Purpose.** Ensure that an `ObservabilityProfile` exists for an onboarded application.

**Signature.**

```python
class DashboardProvisioningService(Protocol):
    def provision(self, app_name: AppName) -> ObservabilityProfile: ...
```

**Behaviour.** Creates (or finds existing) Grafana dashboard from a JSON template, with the dashboard uid `app-<appName>`.

---

## `IdpBuilderService` (external)

Wraps the `./idpbuilder` CLI for cluster lifecycle operations. Used by `boot.sh`, not by the agent. Documented here for completeness.

```python
class IdpBuilderService(Protocol):
    def create(self, cluster_name: str = "demo-cluster") -> Cluster: ...
    def delete(self, cluster_name: str) -> None: ...
    def status(self, cluster_name: str) -> ClusterStatus: ...
```

---

## Service collaboration map

```
OnboardingOrchestrationService
├── IntentExtractionService     ─── OpenRouter ACL
├── StackSelectionService       ─── reads catalog (in-memory)
├── TemplateRenderingService    ─── Jinja2
├── GitHubRepositoryService     ─── GitHub ACL  (PyGithub)
├── GitWorkingCopyService       ─── git CLI ACL
├── KubernetesApplyService      ─── kubectl ACL
├── ArgoApplicationProjectionService ─── kubectl ACL
└── DashboardProvisioningService ── Grafana ACL
```

The orchestration service is the **only** place where collaborations across bounded contexts happen. Everywhere else, each service stays inside its own context and trades only via aggregates and events.
