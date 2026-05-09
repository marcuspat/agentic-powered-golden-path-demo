# 07 — Domain Events

A **Domain Event** is a past-tense fact about something that happened in the domain. Events decouple producers from consumers, make the system observable, and give us a natural audit trail.

This document specifies every event in the model: name, producing aggregate, payload schema, and consumers. Events are first-class even when no code currently consumes them — they reify the *facts* of the system and make tomorrow's automations cheap.

## Event taxonomy

Events use a **PastTense.PastVerb** name pattern: `<NounAggregate>.<PastVerb>`. Examples: `OnboardingRun.Started`, `SourceRepository.Created`, `ArgoApplication.Synced`.

### Categories

- **Lifecycle events** — *X.Created*, *X.Updated*, *X.Deleted* — emitted by aggregate state changes.
- **Workflow events** — *X.Started*, *X.Completed*, *X.Failed* — emitted by long-running operations.
- **Integration events** — *X.Reconciled*, *X.Synced* — observed from external systems via projections.

## Common envelope

Every event ships in a common envelope:

```json
{
  "id":             "uuid-v4",
  "name":           "OnboardingRun.Started",
  "version":        1,
  "occurredAt":     "2026-05-09T10:00:00Z",
  "correlationId":  "uuid-v4 of the OnboardingRun",
  "causationId":    "uuid-v4 of the event that caused this one (optional)",
  "producer":       "agent | argocd | tekton | observability",
  "payload":        { /* event-specific */ }
}
```

In the current CLI implementation, events are emitted as structured log records with these fields. A future server profile may publish them to a CloudEvents bus.

---

## Catalogue

| #  | Event                              | Producer                     | Consumers                              | Status         |
|----|------------------------------------|------------------------------|----------------------------------------|----------------|
| 1  | `OnboardingRun.Started`            | BC-1 Onboarding              | logs, audit                            | Logical        |
| 2  | `OnboardingRun.IntentExtracted`    | BC-1 Onboarding              | logs, BC-2 Stack selection             | Logical        |
| 3  | `OnboardingRun.Completed`          | BC-1 Onboarding              | logs, future Slack notifier            | Logical        |
| 4  | `OnboardingRun.Failed`             | BC-1 Onboarding              | logs, alerting                         | Logical        |
| 5  | `SourceRepository.Created`         | BC-3 Source Provisioning     | BC-1                                   | Logical        |
| 6  | `SourceRepository.Populated`       | BC-3 Source Provisioning     | BC-1, BC-8 (future trigger)            | Logical        |
| 7  | `GitOpsRepository.Created`         | BC-4 GitOps Configuration    | BC-1                                   | Logical        |
| 8  | `GitOpsRepository.Populated`       | BC-4 GitOps Configuration    | BC-1, BC-5                             | Logical        |
| 9  | `GitOpsRepository.Promoted`        | BC-4 (or BC-8 image bumps)   | BC-5 (via ArgoCD)                      | Planned        |
| 10 | `GitOpsRepository.RolledBack`      | Operator                     | BC-5 (via ArgoCD), audit               | Planned        |
| 11 | `ArgoApplication.Registered`       | BC-5 Deployment Orch.        | BC-1, BC-7                             | Logical        |
| 12 | `ArgoApplication.SyncStarted`      | ArgoCD (observed)            | BC-7                                   | External       |
| 13 | `ArgoApplication.Synced`           | ArgoCD (observed)            | BC-7                                   | External       |
| 14 | `ArgoApplication.SyncFailed`       | ArgoCD (observed)            | BC-7, alerting                         | External       |
| 15 | `Workload.Healthy`                 | ArgoCD / k8s (observed)      | BC-7                                   | External       |
| 16 | `Workload.Degraded`                | ArgoCD / k8s (observed)      | BC-7, alerting                         | External       |
| 17 | `ObservabilityProfile.Provisioned` | BC-7 Observability           | logs                                   | Planned        |
| 18 | `PipelineRun.Started`              | BC-8 CI                      | BC-7                                   | Planned        |
| 19 | `PipelineRun.Completed`            | BC-8 CI                      | BC-4 (image bump), BC-7                | Planned        |
| 20 | `Cluster.Ready`                    | BC-6 Platform Provisioning   | (precondition for BC-1)                | External       |

---

## Event details

### 1. `OnboardingRun.Started`

Emitted when `run_onboarding_flow` enters its first instruction.

**Payload:**

```json
{
  "request": "I need to deploy my new NodeJS service called inventory-api",
  "actor":   "developer@github-username"
}
```

### 2. `OnboardingRun.IntentExtracted`

Emitted after `IntentExtractionService` returns successfully (or via fallback).

**Payload:**

```json
{
  "appName":       "inventory-api",
  "stack":         "nodejs",
  "extractionPath": "llm" | "regex" | "default",
  "rawResponse":   "inventory-api"
}
```

### 3. `OnboardingRun.Completed`

Terminal-success event.

**Payload:**

```json
{
  "appName":             "inventory-api",
  "sourceRepoUrl":       "https://github.com/.../inventory-api-source.git",
  "gitopsRepoUrl":       "https://github.com/.../inventory-api-gitops.git",
  "argoApplicationName": "inventory-api",
  "namespace":           "inventory-api",
  "ingressUrl":          "http://inventory-api.cnoe.localtest.me",
  "durationSeconds":     117.3
}
```

### 4. `OnboardingRun.Failed`

Terminal-failure event.

**Payload:**

```json
{
  "appName":     "inventory-api",
  "failedStep":  "populate_repo_from_stack",
  "reason":      "permission denied (HTTP 403): rate-limited by GitHub",
  "stackTrace":  "..."
}
```

### 5. `SourceRepository.Created`

```json
{ "appName": "inventory-api", "url": "https://github.com/.../inventory-api-source.git" }
```

### 6. `SourceRepository.Populated`

```json
{
  "appName":      "inventory-api",
  "url":          "...",
  "stack":        "nodejs",
  "fileCount":    7,
  "commitSha":    "abc123…",
  "commitMessage":"Initial commit from Golden Path Agent"
}
```

### 7. `GitOpsRepository.Created`

Mirror of event 5 for the GitOps repo.

### 8. `GitOpsRepository.Populated`

Mirror of event 6, with additional fields:

```json
{
  "manifestKinds": ["Namespace","Deployment","Service","Ingress","ServiceMonitor"],
  "namespace":     "inventory-api"
}
```

### 9. `GitOpsRepository.Promoted` (planned)

A non-initial commit advancing Desired State.

```json
{ "appName": "inventory-api", "fromSha": "abc…", "toSha": "def…", "reason": "image-bump" }
```

### 10. `GitOpsRepository.RolledBack` (planned)

A `git revert` event.

```json
{ "appName": "inventory-api", "revertedSha": "def…", "newHeadSha": "ghi…", "operator": "alice" }
```

### 11. `ArgoApplication.Registered`

Emitted after `kubectl apply` of the `Application` CR succeeds.

```json
{
  "appName":   "inventory-api",
  "namespace": "inventory-api",
  "repoURL":   "...",
  "syncPolicy": {"automated": true, "prune": true, "selfHeal": true}
}
```

### 12-16. ArgoCD / Workload events

Observed externally (via ArgoCD's notification controller, an event exporter, or a Kubernetes informer). Their payloads mirror ArgoCD's existing notification templates and are translated through an ACL into the schemas above.

### 17. `ObservabilityProfile.Provisioned` (planned)

```json
{
  "appName":         "inventory-api",
  "metricsEndpoint": "/metrics",
  "otlpEndpoint":    "otel-collector.observability.svc.cluster.local:4317",
  "dashboardUid":    "app-inventory-api"
}
```

### 18, 19. PipelineRun events (planned)

Emitted by Tekton via the Tekton Notifications controller (or a custom listener). Translated into our schema through a BC-8 ACL.

### 20. `Cluster.Ready`

Emitted by `idpbuilder` (or a wrapper) once the cluster is up, ArgoCD is healthy, and ingress is serving. Acts as the precondition for any `OnboardingRun.Started`.

---

## Event ordering and causation

Within a single `OnboardingRun`, the **happy-path event order** is:

```
OnboardingRun.Started
  → OnboardingRun.IntentExtracted
  → SourceRepository.Created
    → SourceRepository.Populated
  → GitOpsRepository.Created
    → GitOpsRepository.Populated
  → ArgoApplication.Registered
  → (asynchronously) ArgoApplication.Synced
                    → Workload.Healthy
                      → ObservabilityProfile.Provisioned
  → OnboardingRun.Completed
```

Each event carries the `correlationId` of the run and the `causationId` of its predecessor. The flow is depicted in [`./diagrams/event-flow.md`](./diagrams/event-flow.md).

The agent **may** declare the run `Completed` after `ArgoApplication.Registered` rather than waiting for `Workload.Healthy` — completion semantics are documented per profile (demo: declare complete after registration; production: wait for healthy). This decision is captured in code, not in the event names.

## Event versioning

Events are versioned in the envelope (`version`). Consumers ignore unknown fields. Breaking changes increment the major version and the producer emits *both* versions for one release cycle.

## Storage and retention

In the current CLI, events live only in `stdout` log lines and the agent's exit code. The implementation guide (doc 12) outlines the migration to a structured emitter that can write to:

- A local JSON-Lines file (`~/.golden-path/events.jsonl`).
- A CloudEvents bus (NATS, Kafka).
- A CloudWatch / Stackdriver / Loki pipeline.

The choice of sink is configurable; the events themselves are sink-agnostic.
