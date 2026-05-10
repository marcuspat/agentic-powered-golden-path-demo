# 10 — Application Services

The **Application Layer** sits between the *outside world* (CLI, future HTTP server, Slack bot) and the **domain layer** (aggregates, value objects, domain services). It is thin: it parses input, opens a unit of work, calls one or more domain services, commits or aborts, and returns a transport-friendly result.

Application services **do not contain business rules**. They orchestrate. They translate transport-layer concerns (CLI args, HTTP bodies, JSON) into domain types, and translate domain results back.

This document specifies each application service with its inputs, outputs, error model, and where it lives in the codebase.

## Application service catalogue

| Service                         | Driven by                  | Status     |
|---------------------------------|----------------------------|------------|
| `OnboardingApplicationService`  | CLI (today), HTTP (future) | Implemented (inline) |
| `RollbackApplicationService`    | CLI (`scripts/rollback.sh`)| Partial    |
| `StackQueryApplicationService`  | CLI (planned)              | Planned    |
| `RunHistoryApplicationService`  | CLI (planned)              | Planned    |

---

## `OnboardingApplicationService`

**Purpose.** Drive the `OnboardingOrchestrationService` from a transport layer.

**Inputs.**

```python
@dataclass(frozen=True)
class OnboardingCommand:
    request_text: str
    actor: ActorIdentity        # for audit / correlation
    options: OnboardingOptions  # e.g. force_recreate, dry_run
```

**Outputs.**

```python
@dataclass(frozen=True)
class OnboardingResult:
    correlation_id: CorrelationId
    outcome: Outcome
    app_name: AppName | None
    source_repo_url: RepositoryUrl | None
    gitops_repo_url: RepositoryUrl | None
    argo_application_name: AppName | None
    namespace: Namespace | None
    ingress_url: str | None
    duration_seconds: float
```

**Behaviour.**

1. Parse `OnboardingCommand`. Validate `request_text` (non-empty, length cap).
2. Construct an `OnboardingRequest` value object.
3. Call `OnboardingOrchestrationService.run(request)`.
4. Translate the resulting `OnboardingRun` aggregate into an `OnboardingResult`.
5. Catch any uncaught domain exception and translate to a `Failed` outcome with a structured reason — application code never leaks domain exception types to the transport.

**Error model.** Three outcome shapes only: `Succeeded`, `Failed(reason)`, `Cancelled`. Transport-layer concerns (HTTP status codes, CLI exit codes) are mapped from these in the transport adapter:

| Domain outcome | CLI exit code | HTTP status |
|----------------|---------------|-------------|
| `Succeeded`    | 0             | 201 Created |
| `Failed`       | 1             | 4xx or 5xx  |
| `Cancelled`    | 2             | 499         |

**Idempotency.** Re-issuing the same `OnboardingCommand` is safe — the underlying `*Repository`s (doc 09) treat existing GitHub repos and ArgoCD Applications idempotently.

**Driving today.** `agent.py`'s `__main__` block (`agent.py:228`) is the de facto application service; the migration target moves it to `agent/application/onboarding.py` with the CLI as a thin transport in `agent/cli.py`.

---

## `RollbackApplicationService`

**Purpose.** Roll back an onboarded application to a prior known-good revision (ADR-0019).

**Inputs.**

```python
@dataclass(frozen=True)
class RollbackCommand:
    app_name: AppName
    target_sha: GitSha | None    # if None, revert the last commit
    reason: str
    actor: ActorIdentity
```

**Outputs.**

```python
@dataclass(frozen=True)
class RollbackResult:
    app_name: AppName
    new_head_sha: GitSha
    outcome: Outcome
```

**Behaviour.**

1. Look up the GitOps repository for `app_name`.
2. Compute the revert (or use `target_sha`).
3. `git revert <sha>`; push.
4. Emit `GitOpsRepository.RolledBack`.
5. ArgoCD picks up the change (ADR-0019); the application service does not wait for sync.

**Driving today.** A bash wrapper (`scripts/rollback.sh`) does the imperative `git revert` directly; the service is the target Python implementation.

---

## `StackQueryApplicationService` (planned)

**Purpose.** List available stacks and their declared variables. Useful in CLI (`agent stacks list`) and in a future web UI for self-service.

**Inputs.** None for `list_all`; `StackName` for `describe`.

**Outputs.** A DTO that includes `name`, `version`, declared variables, README excerpt.

---

## `RunHistoryApplicationService` (planned)

**Purpose.** Read past `OnboardingRun` records from the JSONL repository and present a summary.

**Inputs.** Optional filters (`actor`, `since`, `outcome`).

**Outputs.** A list of `OnboardingResult` DTOs.

---

## Cross-cutting concerns

### Transactions

Application services define the unit of work. In this system, unit-of-work is approximated because most aggregates persist into external systems with no native transaction. We mitigate via:

- **Idempotent operations** at the repository layer.
- **Eventual consistency via events**, not synchronous coordination.
- **Compensating actions** documented in [`12-implementation-guide.md`](./12-implementation-guide.md). E.g. on a failed `OnboardingRun`, deleting the GitHub repos is *not* automatic; the failure is logged and an operator decides whether to clean up.

### Authentication & authorisation

Today the agent runs as the local user with their PAT. There is no multi-tenant authn/authz at the application-service layer. When a server profile lands, this section will be expanded with a `Principal` value object and an `AuthorizationPolicy` domain service.

### Telemetry

Each application service:

- Wraps execution in an OTel span named after the service (`onboarding.run`, `rollback.run`).
- Emits the run's `correlationId` as a span attribute.
- Records the resulting outcome on the span.
- Logs structured records compatible with the event envelope in [`07-domain-events.md`](./07-domain-events.md).

### Validation

Validation lives in three places, in order of precedence:

1. **Value objects** — most validation is performed at construction (`AppName`, `RepositoryUrl`, …).
2. **Aggregates** — invariants that span fields are enforced inside the aggregate.
3. **Application services** — only transport-shape validation (e.g. "request_text is a non-empty string"). Anything richer is delegated to value objects.

If you find yourself writing a regex inside an application service, you have probably skipped a value object.

## Layered architecture summary

```
┌────────────────────────────────────────────────────────────────┐
│                         Transport                              │
│   CLI (agent/cli.py)       HTTP (future)       Slack (future)  │
└────────────────────────┬───────────────────────────────────────┘
                         │  parses args, builds Command
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                  Application Layer                             │
│   OnboardingApplicationService    RollbackApplicationService   │
└────────────────────────┬───────────────────────────────────────┘
                         │  calls one or more domain services
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                      Domain Layer                              │
│  Aggregates  Value Objects  Domain Services  Domain Events     │
└────────────────────────┬───────────────────────────────────────┘
                         │  uses ports
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                  Infrastructure / ACLs                         │
│  PyGithub  Jinja2  kubectl  OpenRouter  Grafana  …             │
└────────────────────────────────────────────────────────────────┘
```

Dependencies always point downward; the domain depends on no other layer. ACLs implement domain ports (interfaces) so the domain doesn't know which library is behind them.
