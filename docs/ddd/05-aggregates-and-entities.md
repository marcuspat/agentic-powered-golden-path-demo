# 05 — Aggregates and Entities

An **Aggregate** is a cluster of objects treated as a single unit for the purpose of consistency. Each aggregate has one **root entity** (the only object the outside world references) and a transactional boundary: invariants inside the aggregate hold at all times; invariants between aggregates are eventually consistent.

This document enumerates every aggregate in the system, listing its root entity, internal entities, invariants, and lifecycle.

## Aggregate index

| #  | Aggregate                | Bounded Context                | Root Entity                | Status     |
|----|--------------------------|--------------------------------|----------------------------|------------|
| 1  | OnboardingRun            | BC-1 Onboarding                | `OnboardingRun`            | Implemented (logically) |
| 2  | Stack                    | BC-2 Stack Catalog             | `Stack`                    | Files-on-disk; manifest planned |
| 3  | SourceRepository         | BC-3 Source Provisioning       | `SourceRepository`         | Implemented |
| 4  | GitOpsRepository         | BC-4 GitOps Configuration      | `GitOpsRepository`         | Implemented |
| 5  | ArgoApplication          | BC-5 Deployment Orchestration  | `ArgoApplication`          | Implemented |
| 6  | Workload                 | BC-5 Deployment Orchestration  | `Workload`                 | External (read-only projection of cluster state) |
| 7  | ObservabilityProfile     | BC-7 Observability             | `ObservabilityProfile`     | Planned     |
| 8  | PipelineRun              | BC-8 Continuous Integration    | `PipelineRun`              | Planned     |
| 9  | Cluster                  | BC-6 Platform Provisioning     | `Cluster`                  | External (idpbuilder-managed) |

Detailed structure follows. Diagrams are in [`./diagrams/aggregate-diagram.md`](./diagrams/aggregate-diagram.md).

---

## 1. OnboardingRun

**Bounded context:** BC-1 Onboarding
**Root:** `OnboardingRun`

### Structure

```
OnboardingRun (root)                        ← entity
├── correlationId : CorrelationId           ← VO
├── request : OnboardingRequest             ← VO
├── extractedAppName : AppName              ← VO
├── selectedStack : StackName               ← VO (reference into BC-2)
├── outcome : Outcome                       ← VO
├── steps : List<OnboardingStep>            ← entities, internal
└── timestamps : { startedAt, completedAt } ← VO
```

### Invariants

- `correlationId` is unique and immutable for the lifetime of the run.
- `extractedAppName` is set exactly once, before any step runs, and never changes.
- The `steps` list is append-only; a step transitions `Pending → InProgress → (Succeeded | Failed)`.
- An `OnboardingRun` is `Succeeded` only when every required step is `Succeeded`.
- Once `outcome ∈ {Succeeded, Failed, Cancelled}`, the run is **terminal** and no field may change.

### Lifecycle

`Created → InProgress → (Succeeded | Failed | Cancelled)`

### Relationships

- References `Stack` (BC-2) **by name**.
- Causes the creation of `SourceRepository`, `GitOpsRepository`, `ArgoApplication` aggregates in their respective contexts. The `OnboardingRun` does **not** hold object references to those aggregates; it stores their identifiers.

### Implementation note

Today the run is implicit — it lives only in log lines and the call stack of `run_onboarding_flow()`. The model proposes promoting it to an explicit class with a `correlationId` so that:

- Logs can be filtered by run.
- Future automations can subscribe to `OnboardingRunCompleted` events.
- Failures can be replayed from the last successful step.

---

## 2. Stack

**Bounded context:** BC-2 Stack Catalog
**Root:** `Stack`

### Structure

```
Stack (root)
├── name : StackName                    ← VO  (e.g. "nodejs")
├── version : StackVersion              ← VO  (semver)
├── sourceTemplate : SourceTemplate     ← entity
│   ├── path : TemplatePath
│   └── files : List<RenderableFile>
├── gitOpsTemplate : GitOpsTemplate     ← entity
│   ├── path : TemplatePath
│   └── files : List<RenderableFile>
└── declaredVariables : TemplateVariableSet ← VO
```

### Invariants

- `name` is unique within the catalog.
- `declaredVariables` lists every variable referenced anywhere in either template; rendering with a missing variable is a domain error, not a silent default.
- A `Stack` is *immutable* in memory; new versions are loaded as new `Stack` instances.
- A render is pure: same `(Stack, variables)` produces the same rendered output, byte-for-byte.

### Lifecycle

Loaded at agent startup from `cnoe-stacks/<name>-template/` and `cnoe-stacks/<name>-gitops-template/`. Garbage collected at process exit.

### Implementation note

Today the "Stack" is implicit; the agent uses hard-coded paths. The target is a `stack.yaml` per stack that declares variables and template paths, parsed into the `Stack` aggregate.

---

## 3. SourceRepository

**Bounded context:** BC-3 Source Provisioning
**Root:** `SourceRepository`

### Structure

```
SourceRepository (root)
├── appName : AppName                   ← VO  (the join key)
├── url : RepositoryUrl                 ← VO
├── createdAt : Timestamp               ← VO
├── status : RepoStatus                 ← VO  (Empty | Populated | Failed)
└── initialCommit : CommitMessage?      ← VO
```

### Invariants

- `appName` is set at creation and immutable.
- `status` transitions `Empty → Populated` exactly once via a domain event; reverse transitions are not modeled.
- `url` is canonical (`https://github.com/<user>/<appName>-source.git`) and matches a regex.

### Lifecycle

`Empty → Populated` (success) or `Empty → Failed` (terminal). No deletion in the domain — orphaned GitHub repositories are cleaned up out-of-band.

---

## 4. GitOpsRepository

**Bounded context:** BC-4 GitOps Configuration
**Root:** `GitOpsRepository`

### Structure

```
GitOpsRepository (root)
├── appName : AppName                       ← VO
├── url : RepositoryUrl                     ← VO
├── createdAt : Timestamp                   ← VO
├── status : RepoStatus                     ← VO (Empty | Populated | Failed)
├── targetNamespace : Namespace             ← VO
├── manifests : List<ManifestKind>          ← VO
└── initialCommit : CommitMessage?          ← VO
```

### Invariants

- Same identity rules as `SourceRepository`.
- `manifests` lists the *kinds* of manifests known to be present (`Deployment`, `Service`, `Ingress`, `Namespace`, `NetworkPolicy`, `ServiceMonitor`, …) — used for validation and observability provisioning.
- `targetNamespace` defaults to `appName` (ADR-0017) and must satisfy DNS-label constraints.

### Lifecycle

Same as `SourceRepository`: `Empty → Populated` or `Empty → Failed`.

---

## 5. ArgoApplication

**Bounded context:** BC-5 Deployment Orchestration
**Root:** `ArgoApplication`

### Structure

```
ArgoApplication (root)
├── name : AppName                              ← VO
├── projectName : ArgoProjectName               ← VO  (default "default")
├── source : ArgoSource                         ← VO
│   ├── repoURL : RepositoryUrl
│   ├── targetRevision : GitRef                 (default "HEAD")
│   └── path : RepoPath                         (default ".")
├── destination : ArgoDestination               ← VO
│   ├── server : ClusterServer                  (default "https://kubernetes.default.svc")
│   └── namespace : Namespace
├── syncPolicy : SyncPolicy                     ← VO
│   ├── automated : { prune, selfHeal }
│   └── syncOptions : List<SyncOption>          (e.g. CreateNamespace=true)
├── syncStatus : SyncStatus                     ← VO  (Synced | OutOfSync | Unknown)
└── healthStatus : HealthStatus                 ← VO  (Healthy | Progressing | Degraded | …)
```

### Invariants

- `name` equals the onboarding `AppName`; no aliasing.
- `destination.namespace` equals `name` by convention (ADR-0017).
- `syncPolicy.automated.prune` and `selfHeal` are both `true` for the default profile.
- `syncStatus` and `healthStatus` are **read-only projections** of cluster state; they are not mutated by the agent.

### Lifecycle

- *Created* by the agent applying the `Application` CR.
- *Synced* by ArgoCD (one or more times).
- *Healthy* once Workload reconciliation completes.
- *Deleted* via `git revert` of the Argo Application manifest, or `kubectl delete application <name> -n argocd`.

---

## 6. Workload

**Bounded context:** BC-5 Deployment Orchestration (read-only)
**Root:** `Workload`

### Structure

```
Workload (root)
├── appName : AppName
├── namespace : Namespace
├── deploymentName : DeploymentName
├── desiredReplicas : ReplicaCount
├── readyReplicas : ReplicaCount
├── image : ContainerImage
└── healthStatus : HealthStatus
```

### Invariants

`Workload` is a **projection** of cluster state. It has no transactional invariants of its own; the cluster is the source of truth. Code that constructs a `Workload` reads it from Kubernetes and does not write it back.

---

## 7. ObservabilityProfile (planned)

**Bounded context:** BC-7 Observability
**Root:** `ObservabilityProfile`

### Structure

```
ObservabilityProfile (root)
├── appName : AppName
├── metricsEndpoint : MetricsEndpoint
├── otlpEndpoint : OtlpEndpoint
├── dashboardUid : DashboardUid
└── createdAt : Timestamp
```

### Invariants

- One `ObservabilityProfile` per onboarded application.
- `dashboardUid` is deterministic from `appName` so dashboards can be looked up without a registry.

---

## 8. PipelineRun (planned)

**Bounded context:** BC-8 Continuous Integration
**Root:** `PipelineRun`

### Structure

```
PipelineRun (root)
├── appName : AppName
├── runId : PipelineRunId
├── triggeringCommit : GitSha
├── steps : List<PipelineStep>
├── builtImage : ContainerImage?
└── outcome : Outcome
```

### Invariants

- `runId` is unique within the cluster.
- `steps` is append-only; same shape as `OnboardingRun.steps`.
- A `PipelineRun` may emit a `GitOpsImageBumped` event that mutates the `GitOpsRepository`.

---

## 9. Cluster (external)

Treated as opaque outside BC-6. Modeled here only as a value object pair `(KubeConfigPath, ClusterName)` — implementations rely on the kube-client to do real work.

---

## Aggregate sizing rules

These rules guide future modeling decisions:

1. **An aggregate fits in a single transaction.** If we'd need a distributed transaction to keep two things consistent, they belong to one aggregate.
2. **External objects (Kubernetes resources, GitHub repos, ArgoCD CRs) are projections.** The aggregate captures *our* model of the desired state. Reconciliation between desired and actual is delegated to ArgoCD or to projection code.
3. **Cross-aggregate consistency is eventual.** A `SourceRepository` may exist before the `GitOpsRepository` does; the `OnboardingRun` aggregate enforces ordering through events, not transactions.
4. **References between aggregates use identifiers, not pointers.** `ArgoApplication` carries a `RepositoryUrl`, not a `GitOpsRepository` object reference.
