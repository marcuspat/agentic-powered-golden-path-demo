# 06 — Value Objects

A **Value Object** is an immutable, equality-by-value type that models a concept without an identity. Value Objects carry domain rules (validation, normalisation, formatting) and prevent the *primitive obsession* anti-pattern where strings and ints stand in for richer concepts.

This document catalogues every value object in the model. Each entry includes: shape, validation rules, normalisation behaviour, and Python typing sketch. Implementations should be `@dataclass(frozen=True)` or `pydantic` `BaseModel(frozen=True)` so equality and immutability are enforced by the type system.

## Catalogue

| Name                    | Bounded Context        | Underlying type      | Used by                                    |
|-------------------------|------------------------|----------------------|--------------------------------------------|
| `AppName`               | Cross-cutting (BC-1)   | `str`                | All aggregates                             |
| `OnboardingRequest`     | BC-1                   | `str`                | `OnboardingRun`                            |
| `Outcome`               | BC-1                   | enum + reason        | `OnboardingRun`, `PipelineRun`             |
| `CorrelationId`         | Cross-cutting          | `UUID`               | `OnboardingRun`, all events                |
| `Timestamp`             | Cross-cutting          | `datetime` (UTC)     | All aggregates                             |
| `StackName`             | BC-2                   | `str`                | `Stack`, `OnboardingRun`                   |
| `StackVersion`          | BC-2                   | `str` (semver)       | `Stack`                                    |
| `TemplatePath`          | BC-2                   | `Path`               | `Stack`                                    |
| `TemplateVariableSet`   | BC-2                   | `frozenset[str]`     | `Stack`                                    |
| `RenderableFile`        | BC-2                   | `(path, bytes)`      | `Stack`                                    |
| `RepositoryUrl`         | BC-3, BC-4             | `str`                | `SourceRepository`, `GitOpsRepository`, `ArgoApplication` |
| `BranchName`            | BC-3, BC-4             | `str`                | Repositories                               |
| `CommitMessage`         | BC-3, BC-4             | `str`                | Repositories                               |
| `GitSha`                | BC-3, BC-4, BC-8       | `str` (40 hex chars) | Repositories, `PipelineRun`                |
| `RepoStatus`            | BC-3, BC-4             | enum                 | Repositories                               |
| `Namespace`             | BC-4, BC-5, BC-7       | `str`                | `GitOpsRepository`, `ArgoApplication`, `Workload` |
| `ManifestKind`          | BC-4                   | enum                 | `GitOpsRepository`                         |
| `ContainerImage`        | BC-4, BC-8             | `str`                | `Workload`, `PipelineRun`                  |
| `ImageTag`              | BC-8                   | `str`                | `PipelineRun`                              |
| `ArgoProjectName`       | BC-5                   | `str`                | `ArgoApplication`                          |
| `ArgoSource`            | BC-5                   | composite            | `ArgoApplication`                          |
| `ArgoDestination`       | BC-5                   | composite            | `ArgoApplication`                          |
| `SyncPolicy`            | BC-5                   | composite            | `ArgoApplication`                          |
| `SyncStatus`            | BC-5                   | enum                 | `ArgoApplication`                          |
| `HealthStatus`          | BC-5                   | enum                 | `ArgoApplication`, `Workload`              |
| `ReplicaCount`          | BC-5                   | `int (≥ 0)`          | `Workload`                                 |
| `ClusterServer`         | BC-5                   | URL                  | `ArgoApplication`                          |
| `MetricsEndpoint`       | BC-7                   | path                 | `ObservabilityProfile`                     |
| `OtlpEndpoint`          | BC-7                   | URL                  | `ObservabilityProfile`                     |
| `DashboardUid`          | BC-7                   | `str`                | `ObservabilityProfile`                     |
| `KubeConfigPath`        | BC-6                   | `Path`               | platform plumbing                          |

---

## Detailed specifications

### `AppName`

The most important value object. Acts as the **join key** across every bounded context.

**Rules:**

- Lowercase ASCII only.
- Allowed characters: `a-z`, `0-9`, `-` (hyphen).
- Must start and end with `[a-z0-9]`.
- Length: 1-63 characters (RFC 1123 DNS label limit; matches Kubernetes name constraints).
- No consecutive hyphens are recommended; collapsed by normaliser.

**Construction:**

- Direct construction validates and rejects invalid input.
- A separate `AppName.from_raw(raw: str) -> AppName` normaliser performs lowercasing, character stripping, hyphen-collapsing, and trim. This is the *only* sanctioned sanitiser; both the LLM path and the regex path in `IntentExtractionService` route through it.

**Equality:** value-based; two `AppName("inventory-api")` are equal regardless of construction path.

**Sketch:**

```python
@dataclass(frozen=True)
class AppName:
    value: str

    _PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")

    def __post_init__(self) -> None:
        if not self._PATTERN.fullmatch(self.value):
            raise ValueError(f"Invalid AppName: {self.value!r}")

    @classmethod
    def from_raw(cls, raw: str) -> "AppName":
        s = raw.strip().lower()
        s = re.sub(r"[^a-z0-9-]", "", s)
        s = re.sub(r"-+", "-", s).strip("-")
        if not s:
            raise ValueError("Empty AppName after normalisation")
        return cls(s[:63])

    def __str__(self) -> str:
        return self.value
```

---

### `OnboardingRequest`

Wraps the raw user utterance. Carries no parsing logic; that's the `IntentExtractionService`.

**Rules:** non-empty after `strip()`, ≤ 4 KiB.

---

### `Outcome`

```python
class OutcomeKind(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED    = "failed"
    CANCELLED = "cancelled"

@dataclass(frozen=True)
class Outcome:
    kind: OutcomeKind
    reason: str | None = None        # required when kind != SUCCEEDED
    failed_step: str | None = None    # name of the step that failed
```

**Invariant:** if `kind == FAILED`, `reason` and `failed_step` are required.

---

### `CorrelationId`

A `UUIDv4` generated at the start of an `OnboardingRun`. Threaded through:

- Every log line (`extra={"correlation_id": …}`).
- Every domain event payload.
- HTTP headers in any future server profile (`X-Correlation-Id`).

---

### `RepositoryUrl`

Canonical HTTPS form: `https://github.com/<user>/<repo>.git`.

**Rules:**

- Must be HTTPS.
- Must end with `.git`.
- Path segments: exactly two (owner / repo).

**Helpers:**

- `RepositoryUrl.from_app(app_name: AppName, kind: Literal["source","gitops"], owner: str) -> RepositoryUrl` builds the canonical URL.
- `RepositoryUrl.repo_name -> str` returns the bare repo name (`<app>-source` etc.).

---

### `Namespace`

Same constraints as `AppName` (DNS label). Often equals `AppName.value` (ADR-0017) but kept distinct as a value type so the model is explicit about *what role* a string plays.

---

### `ContainerImage`

```python
@dataclass(frozen=True)
class ContainerImage:
    registry: str   # e.g. "ghcr.io"
    repository: str # e.g. "acme/inventory-api"
    tag: ImageTag   # e.g. ImageTag("v1.2.3")

    def __str__(self) -> str:
        return f"{self.registry}/{self.repository}:{self.tag.value}"
```

**Rules:**

- `tag` is never `latest` in production manifests; warn at validation if encountered.
- Digest form (`@sha256:…`) is permitted; modeled by an `ImageDigest` sibling type if needed.

---

### `SyncPolicy`

```python
@dataclass(frozen=True)
class SyncPolicy:
    automated: bool = True
    prune: bool = True
    self_heal: bool = True
    create_namespace: bool = True
```

Default is the project standard (ADR-0003, ADR-0017). Variations are allowed but must justify themselves in code review.

---

### `HealthStatus` and `SyncStatus`

Both are enums mirroring ArgoCD's vocabulary:

```python
class HealthStatus(str, Enum):
    HEALTHY     = "Healthy"
    PROGRESSING = "Progressing"
    DEGRADED    = "Degraded"
    SUSPENDED   = "Suspended"
    MISSING     = "Missing"
    UNKNOWN     = "Unknown"

class SyncStatus(str, Enum):
    SYNCED     = "Synced"
    OUT_OF_SYNC = "OutOfSync"
    UNKNOWN    = "Unknown"
```

Imported types from ArgoCD's CRD; kept inside the **ACL** so that, if ArgoCD adds a new value, only the ACL's mapping updates.

---

### `Timestamp`

Always UTC. Always ISO-8601 in serialised form. Never naive `datetime`.

```python
@dataclass(frozen=True)
class Timestamp:
    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None:
            raise ValueError("Timestamp must be tz-aware")

    @classmethod
    def now(cls) -> "Timestamp":
        return cls(datetime.now(tz=timezone.utc))
```

---

## Why so many value objects?

Each line below is a real bug we want to prevent at compile/construction time:

- `repo_url = "github.com/user/inventory-api"` — missing `https://` and `.git`. `RepositoryUrl` rejects it.
- `app_name = "Inventory API"` — uppercase + space. `AppName` rejects it.
- `namespace = "default"` for app `inventory-api` — convention violated. Code review should challenge it; the type does not yet enforce it (we prefer convention over hard fail to keep rollouts flexible).
- `image_tag = "latest"` — silent. `ContainerImage` warns.
- `timestamps_str = "2026-05-09 10:00"` — naive, ambiguous. `Timestamp` rejects it.

The cost of these classes is one file (`agent/domain/values.py`); the benefit is that *every* string flowing through the agent has a type that says what it is and what it must look like.
