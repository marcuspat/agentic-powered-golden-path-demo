# 09 — Repositories

In DDD, a **Repository** abstracts the persistence and retrieval of an aggregate. From the domain's point of view, a repository looks like an in-memory collection: `add(aggregate)`, `get(id)`, `find_by(...)`. Where the data actually lives — a database, a file, a remote API — is an infrastructure concern hidden behind the interface.

Most aggregates in this system are *not* persisted by us; they live in external systems (GitHub, Kubernetes API). Our "repositories" are therefore **adapters that translate aggregates to and from those external systems**. They sit at the boundary between the domain and infrastructure layers.

This document specifies each repository: aggregate, interface, backing store, and current implementation status.

## Repository catalogue

| Repository                       | Aggregate                | Backing Store                     | Status     |
|----------------------------------|--------------------------|-----------------------------------|------------|
| `OnboardingRunRepository`        | `OnboardingRun`          | In-memory + JSONL log (planned)   | Planned    |
| `StackRepository`                | `Stack`                  | Filesystem (`cnoe-stacks/`)       | Implemented (implicit) |
| `SourceRepositoryRepository`     | `SourceRepository`       | GitHub API                        | Implemented (inline) |
| `GitOpsRepositoryRepository`     | `GitOpsRepository`       | GitHub API                        | Implemented (inline) |
| `ArgoApplicationRepository`      | `ArgoApplication`        | Kubernetes API (`Application` CR) | Implemented (inline) |
| `WorkloadRepository`             | `Workload` (read-only)   | Kubernetes API (`Deployment`)     | Planned    |
| `ObservabilityProfileRepository` | `ObservabilityProfile`   | Grafana API + Prometheus CRDs     | Planned    |

The naming `XRepository` is a domain term, not a class-naming convention; in code these may be split into adapter classes (`GitHubRepoAdapter` + `SourceRepositoryRepository` ports) — see [`11-anti-corruption-layers.md`](./11-anti-corruption-layers.md).

---

## `OnboardingRunRepository` (planned)

**Aggregate:** `OnboardingRun`

**Interface:**

```python
class OnboardingRunRepository(Protocol):
    def add(self, run: OnboardingRun) -> None: ...
    def get(self, correlation_id: CorrelationId) -> OnboardingRun: ...
    def list_recent(self, limit: int = 50) -> List[OnboardingRun]: ...
```

**Backing store.** Two-level:

1. **In-memory** for the lifetime of the CLI process (today this is the call stack).
2. **JSON-Lines append-only log** at `~/.golden-path/runs.jsonl` for cross-process continuity (planned).

**Rationale.** The agent is short-lived; persistence is needed only for audit and replay. JSONL is human-readable and easy to query with `jq`.

**Side effects.** Append to the log file; rotation handled by `logrotate` if/when the log grows.

---

## `StackRepository`

**Aggregate:** `Stack`

**Interface:**

```python
class StackRepository(Protocol):
    def get(self, name: StackName) -> Stack: ...
    def list_all(self) -> List[Stack]: ...
```

**Backing store.** The filesystem under `cnoe-stacks/`. The repository:

1. Lists subdirectories matching `*-template/` and `*-gitops-template/`.
2. Pairs source and gitops templates by stack name (e.g. `nodejs-template/` ↔ `nodejs-gitops-template/`).
3. Reads `stack.yaml` (when introduced) for declared variables and version metadata.
4. Loads file contents lazily.

**Side effects.** Filesystem reads only.

**Caching.** All `Stack` objects can be cached for the process lifetime; the catalog does not change at runtime.

---

## `SourceRepositoryRepository`

**Aggregate:** `SourceRepository`

**Interface:**

```python
class SourceRepositoryRepository(Protocol):
    def create(self, app_name: AppName, description: AppDescription) -> SourceRepository: ...
    def get(self, app_name: AppName) -> SourceRepository | None: ...
    def populate(self, repo: SourceRepository, files: List[RenderedFile], commit: CommitMessage) -> SourceRepository: ...
```

**Backing store.** GitHub via `PyGithub` and `git` CLI (the latter for push). The repository internally uses `GitHubRepositoryService` and `GitWorkingCopyService` (see doc 08).

**Idempotency.** `create` is idempotent on existing repository names: returns the existing aggregate with `RepoStatus.Empty` (the agent then re-populates).

**Side effects.** Creates a real GitHub repository; pushes a commit. Non-reversible from the agent's side.

---

## `GitOpsRepositoryRepository`

**Aggregate:** `GitOpsRepository`

Mirror of `SourceRepositoryRepository` but creates `<app>-gitops` and populates with rendered GitOps templates. Same backing store and idempotency rules.

---

## `ArgoApplicationRepository`

**Aggregate:** `ArgoApplication`

**Interface:**

```python
class ArgoApplicationRepository(Protocol):
    def add(self, app: ArgoApplication) -> None: ...        # creates the CR
    def get(self, app_name: AppName) -> ArgoApplication | None: ...   # reads the CR + status
    def remove(self, app_name: AppName) -> None: ...        # deletes the CR
```

**Backing store.** Kubernetes API. `add` materialises the aggregate into an `Application` YAML and applies it via `KubernetesApplyService`. `get` reads the CR and translates ArgoCD status fields through the BC-5 ACL.

**Side effects.** Mutates cluster state.

**Note on consistency.** `add` returns once the `Application` CR is registered; it does **not** wait for sync. Sync status is observed asynchronously via `WorkloadRepository` and ArgoCD events.

---

## `WorkloadRepository` (planned)

**Aggregate:** `Workload` (read-only projection)

**Interface:**

```python
class WorkloadRepository(Protocol):
    def get(self, app_name: AppName) -> Workload | None: ...
    def wait_for_health(self, app_name: AppName, *, timeout: timedelta) -> Workload: ...
```

**Backing store.** Kubernetes API. Reads `Deployment` and `Pod` resources in the app's namespace; computes `desired/ready` replica counts and a `HealthStatus`.

**Side effects.** None (read-only).

---

## `ObservabilityProfileRepository` (planned)

**Aggregate:** `ObservabilityProfile`

**Interface:**

```python
class ObservabilityProfileRepository(Protocol):
    def add(self, profile: ObservabilityProfile) -> None: ...
    def get(self, app_name: AppName) -> ObservabilityProfile | None: ...
```

**Backing store.** Grafana HTTP API for dashboards; Kubernetes API for `ServiceMonitor` and `PodMonitor` CRs.

---

## Implementation conventions

1. **One repository per aggregate.** Don't create grab-bag repositories that span multiple aggregates.
2. **Repositories return aggregates, never raw infrastructure types.** A `SourceRepositoryRepository.get()` returns a `SourceRepository`, never a `PyGithub.Repository`.
3. **Repository methods raise domain exceptions.** `RepositoryQuotaExceeded`, `Unauthorized`, `RateLimited`, `K8sApplyError` — never let `requests.HTTPError` or `kubernetes.client.exceptions.ApiException` leak past the repository boundary.
4. **Idempotency where possible.** Demos re-run; tests re-run. `add` and `create` should be safe to call twice with the same arguments.
5. **No business rules in repositories.** They are persistence shims; rules live in aggregates and domain services.

## Mapping to current code

| Repository                       | Today (location)                                                                | Migration target                                  |
|----------------------------------|----------------------------------------------------------------------------------|---------------------------------------------------|
| `OnboardingRunRepository`        | none (logs only)                                                                 | `agent/infrastructure/runs/jsonl_repo.py`         |
| `StackRepository`                | implicit path-walk in `populate_repo_from_stack()`                               | `agent/infrastructure/catalog/fs_repo.py`         |
| `SourceRepositoryRepository`     | `create_github_repo()` + `populate_repo_from_stack()` (`agent.py:15`, `:44`)     | `agent/infrastructure/github/source_repo.py`      |
| `GitOpsRepositoryRepository`     | same functions, second invocation                                                | `agent/infrastructure/github/gitops_repo.py`      |
| `ArgoApplicationRepository`      | `create_argocd_application()` (`agent.py:91`)                                    | `agent/infrastructure/k8s/argo_repo.py`           |
| `WorkloadRepository`             | none                                                                              | `agent/infrastructure/k8s/workload_repo.py`       |
| `ObservabilityProfileRepository` | none                                                                              | `agent/infrastructure/grafana/dashboard_repo.py`  |
