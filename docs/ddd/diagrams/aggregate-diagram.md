# Aggregate Diagrams

This document supplements [`../05-aggregates-and-entities.md`](../05-aggregates-and-entities.md) with structural and lifecycle diagrams. All diagrams are Mermaid for native GitHub rendering.

## Aggregates and their identifiers

```mermaid
classDiagram
    class OnboardingRun {
        +CorrelationId correlationId
        +OnboardingRequest request
        +AppName extractedAppName
        +StackName selectedStack
        +Outcome outcome
        +Timestamp startedAt
        +Timestamp completedAt
        +start()
        +recordExtractedIntent()
        +recordStepCompleted()
        +complete()
        +fail()
    }

    class Stack {
        +StackName name
        +StackVersion version
        +TemplateVariableSet declaredVariables
        +SourceTemplate sourceTemplate
        +GitOpsTemplate gitOpsTemplate
    }

    class SourceRepository {
        +AppName appName
        +RepositoryUrl url
        +RepoStatus status
        +CommitMessage initialCommit
        +Timestamp createdAt
        +markPopulated()
        +markFailed()
    }

    class GitOpsRepository {
        +AppName appName
        +RepositoryUrl url
        +RepoStatus status
        +Namespace targetNamespace
        +ManifestKind[] manifests
        +Timestamp createdAt
        +markPopulated()
        +markFailed()
    }

    class ArgoApplication {
        +AppName name
        +ArgoSource source
        +ArgoDestination destination
        +SyncPolicy syncPolicy
        +SyncStatus syncStatus
        +HealthStatus healthStatus
    }

    class Workload {
        +AppName appName
        +Namespace namespace
        +ContainerImage image
        +ReplicaCount desired
        +ReplicaCount ready
        +HealthStatus health
    }

    class ObservabilityProfile {
        +AppName appName
        +MetricsEndpoint metricsEndpoint
        +OtlpEndpoint otlpEndpoint
        +DashboardUid dashboardUid
    }

    class PipelineRun {
        +AppName appName
        +PipelineRunId runId
        +GitSha triggeringCommit
        +ContainerImage builtImage
        +Outcome outcome
    }

    OnboardingRun ..> Stack : references by name
    OnboardingRun ..> SourceRepository : causes
    OnboardingRun ..> GitOpsRepository : causes
    OnboardingRun ..> ArgoApplication : causes
    GitOpsRepository ..> ArgoApplication : referenced by
    ArgoApplication ..> Workload : results in
    Workload ..> ObservabilityProfile : observed by
    SourceRepository ..> PipelineRun : triggers
    PipelineRun ..> GitOpsRepository : commits image bumps to
```

## Aggregate boundaries

Each box in the diagram below is one aggregate (transactional consistency boundary). Lines between boxes represent **eventually consistent** relationships.

```mermaid
flowchart LR
    subgraph BC1["BC-1 Onboarding"]
        OR["OnboardingRun
        + CorrelationId
        + steps[]"]
    end

    subgraph BC2["BC-2 Stack Catalog"]
        S["Stack
        + SourceTemplate
        + GitOpsTemplate"]
    end

    subgraph BC3["BC-3 Source Provisioning"]
        SR["SourceRepository"]
    end

    subgraph BC4["BC-4 GitOps Configuration"]
        GR["GitOpsRepository
        + manifests
        + namespace"]
    end

    subgraph BC5["BC-5 Deployment Orchestration"]
        AA["ArgoApplication"]
        WL["Workload (projection)"]
    end

    subgraph BC7["BC-7 Observability"]
        OP["ObservabilityProfile"]
    end

    subgraph BC8["BC-8 Continuous Integration"]
        PR["PipelineRun"]
    end

    OR -. by AppName .-> SR
    OR -. by AppName .-> GR
    OR -. by AppName .-> AA
    OR -. by StackName .-> S

    GR -. by RepositoryUrl .-> AA
    AA -. by AppName .-> WL
    WL -. by AppName .-> OP

    SR -. by AppName .-> PR
    PR -. by AppName, image bump .-> GR
```

## State machines

### `OnboardingRun`

```mermaid
stateDiagram-v2
    [*] --> Created
    Created --> InProgress: start()
    InProgress --> InProgress: recordStepCompleted()
    InProgress --> Succeeded: complete()
    InProgress --> Failed: fail(reason)
    InProgress --> Cancelled: cancel()
    Succeeded --> [*]
    Failed --> [*]
    Cancelled --> [*]
```

### `SourceRepository` and `GitOpsRepository`

```mermaid
stateDiagram-v2
    [*] --> Empty
    Empty --> Populated: markPopulated(commit)
    Empty --> Failed: markFailed()
    Populated --> [*]
    Failed --> [*]
```

### `ArgoApplication` (status projected from cluster)

```mermaid
stateDiagram-v2
    [*] --> Registered
    Registered --> OutOfSync: ArgoCD detects drift
    Registered --> Synced: ArgoCD syncs
    OutOfSync --> Synced: ArgoCD syncs
    Synced --> OutOfSync: drift / new commit
    Synced --> [*]: deletion
```

### `Workload` health (read-only projection)

```mermaid
stateDiagram-v2
    [*] --> Missing
    Missing --> Progressing: pods scheduled
    Progressing --> Healthy: readiness OK
    Progressing --> Degraded: probe failures
    Healthy --> Progressing: rollout
    Healthy --> Degraded: probe regression
    Degraded --> Progressing: rollback / fix
    Healthy --> [*]
```

### `PipelineRun` (planned)

```mermaid
stateDiagram-v2
    [*] --> Pending
    Pending --> Running: dispatched
    Running --> Succeeded: all tasks pass
    Running --> Failed: any task fails
    Succeeded --> [*]
    Failed --> [*]
```

## Why these boundaries?

- `OnboardingRun` does **not** contain the repositories or the ArgoApplication. They are referenced by name; their lifecycle is independent. A failed `OnboardingRun` may leave behind valid `SourceRepository` and `GitOpsRepository` artefacts that an operator can clean up or recover.
- `Stack` is a *read* aggregate; it never owns mutable state at runtime.
- `SourceRepository` and `GitOpsRepository` are **separate aggregates** because they enforce different invariants and because their lifecycles diverge after creation (one receives application code commits, the other receives image bumps and operator promotions).
- `Workload` is a **projection**, not an aggregate we own. It is included in the model so we can talk about it, but its source of truth is the Kubernetes API.
