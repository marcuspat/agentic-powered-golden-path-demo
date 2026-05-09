# 11 — Anti-Corruption Layers

An **Anti-Corruption Layer (ACL)** is a translation layer that prevents a foreign model from contaminating the domain. The agent integrates with five external systems — GitHub, OpenRouter, Kubernetes, ArgoCD, and (future) Tekton/Grafana. Each speaks a model that is rich, opinionated, and **theirs, not ours**. Without ACLs, the foreign model creeps into our code: we end up passing `PyGithub.Repository` objects to functions that should be passing `SourceRepository`, and our domain becomes whatever those libraries happen to expose.

This document specifies the ACL between each external system and our domain, including:

- Which foreign types are translated.
- Where the boundary sits in the layered architecture.
- How errors are translated into domain exceptions.

## ACL inventory

| Foreign system     | Foreign types                                                                  | Domain types it translates to                                            |
|--------------------|--------------------------------------------------------------------------------|---------------------------------------------------------------------------|
| GitHub (PyGithub)  | `Repository`, `AuthenticatedUser`, `GithubException`                          | `SourceRepository`, `GitOpsRepository`, `RepositoryUrl`, domain errors    |
| OpenRouter (`openai` SDK) | `ChatCompletion`, `OpenAIError`                                          | `ExtractedIntent`, domain errors                                          |
| `git` CLI           | exit codes, stderr blobs                                                       | `GitSha`, `CommitMessage`, domain errors                                  |
| Kubernetes (`kubectl` + `kubernetes` SDK) | `V1Deployment`, `client.exceptions.ApiException`, raw YAML | `ArgoApplication`, `Workload`, `Namespace`, domain errors             |
| ArgoCD (Application CR) | `argoproj.io/v1alpha1 Application` JSON                                  | `ArgoApplication.{syncStatus, healthStatus}`                              |
| Tekton (planned)   | `tekton.dev/v1beta1 PipelineRun` JSON                                          | `PipelineRun`, `BuildResult`                                              |
| Grafana (planned)  | dashboard JSON, HTTP error responses                                            | `ObservabilityProfile`, `DashboardUid`                                    |

---

## The GitHub ACL

**Foreign types crossing the boundary:**

- `github.Repository.Repository` (the PyGithub class).
- `github.GithubException` and subclasses (`UnknownObjectException`, `RateLimitExceededException`, `BadCredentialsException`).

**Adapter:** `agent/infrastructure/github/adapter.py` (target location).

**Translation rules:**

| Foreign                                              | Domain                                                                |
|------------------------------------------------------|-----------------------------------------------------------------------|
| `Repository.clone_url`                               | `RepositoryUrl(str)`                                                  |
| `Repository.full_name.split("/")[1]`                 | identity component for `AppName` lookup                               |
| `Repository.created_at`                              | `Timestamp`                                                           |
| `RateLimitExceededException`                         | `RateLimited(retry_after: timedelta)` domain error                    |
| `BadCredentialsException`                            | `Unauthorized` domain error                                           |
| `GithubException(422, "name already exists")`        | not an error: returns the canonical URL via `RepositoryUrl.from_app`  |
| Any other `GithubException`                          | `ExternalSystemError("github", original=e)` domain error              |

**Inverse translation:** `RepositoryUrl` → repository name + owner are extracted by string operations; the adapter never re-fetches the foreign object once translated.

**Why this matters.** Without the ACL, `populate_repo_from_stack(repo: Repository)` would pull PyGithub into every test that touches repositories; our test suite would mock PyGithub instead of the small domain interface.

---

## The OpenRouter ACL

**Foreign types crossing the boundary:**

- `openai.OpenAI` client.
- `ChatCompletion`, `Choice`, `Message`.
- `openai.OpenAIError` subclasses (`APIError`, `RateLimitError`, `AuthenticationError`, `APIConnectionError`).

**Adapter:** `agent/infrastructure/openrouter/adapter.py` (target).

**Translation rules:**

| Foreign                                          | Domain                                                                 |
|--------------------------------------------------|------------------------------------------------------------------------|
| `ChatCompletion.choices[0].message.content`      | `str` → `AppName.from_raw(...)` → `ExtractedIntent`                    |
| `RateLimitError`                                 | `LlmUnavailable("rate limited")` triggering regex fallback             |
| `AuthenticationError`                            | `LlmUnavailable("auth")` triggering regex fallback                     |
| `APIConnectionError`                             | `LlmUnavailable("network")` triggering regex fallback                  |
| Empty / malformed completion                     | `LlmUnavailable("malformed response")`                                 |

The adapter **never raises** non-domain exceptions to its caller. Every error funnels into one domain type (`LlmUnavailable`), which the `IntentExtractionService` catches to perform fallback.

---

## The git CLI ACL

**Foreign:** the `git` CLI returning exit codes and dumping stderr text.

**Adapter:** `agent/infrastructure/git/adapter.py` (target).

**Translation rules:**

| Foreign                                                    | Domain                                                       |
|------------------------------------------------------------|--------------------------------------------------------------|
| `git rev-parse HEAD` stdout                                | `GitSha(value)`                                              |
| `git commit` returning non-zero with "nothing to commit"   | not an error: returns the existing HEAD `GitSha`             |
| `git push` returning non-zero with auth failure           | `Unauthorized` domain error                                  |
| `git push` returning non-zero with non-fast-forward        | `GitOutOfDate` domain error                                  |
| Any other non-zero exit                                    | `ExternalSystemError("git", original=stderr)` domain error  |

**Subprocess hygiene.** All invocations use `subprocess.run([...], check=False, capture_output=True)` and **list-form** arguments. No string command construction crosses the boundary; this is the ACL's contract with the security model (ADR-0004).

---

## The Kubernetes / ArgoCD ACL

**Foreign:** `kubectl apply` exit codes and the `kubernetes` Python SDK.

**Adapter:** `agent/infrastructure/k8s/adapter.py` (target).

**Translation rules — apply path (write):**

| Foreign                                            | Domain                                                                |
|----------------------------------------------------|-----------------------------------------------------------------------|
| `kubectl apply` exit 0                             | `None` (success)                                                       |
| `kubectl apply` exit non-zero                      | `K8sApplyError(message=stderr)`                                        |
| Auth failure                                       | `Unauthorized`                                                          |

**Translation rules — read path (project ArgoCD `Application` status):**

| Foreign (Application status field)                | Domain                                                                |
|---------------------------------------------------|-----------------------------------------------------------------------|
| `status.sync.status == "Synced"`                  | `SyncStatus.SYNCED`                                                    |
| `status.sync.status == "OutOfSync"`               | `SyncStatus.OUT_OF_SYNC`                                               |
| any other / missing                               | `SyncStatus.UNKNOWN`                                                   |
| `status.health.status == "Healthy"`               | `HealthStatus.HEALTHY`                                                 |
| `status.health.status == "Degraded"`              | `HealthStatus.DEGRADED`                                                |
| any other / missing                               | `HealthStatus.UNKNOWN`                                                 |

The translation is one-way: ArgoCD vocabulary → our enum. If ArgoCD ever introduces a new status value, only this table updates.

**Inverse translation:** `ArgoApplication` → YAML manifest. The adapter constructs the YAML from value-object fields, never via dict-literals scattered through the domain.

---

## Why we don't trust the SDKs alone

Every SDK is a leaky abstraction:

- **PyGithub** raises `Github.Exception` *as well as* `requests.exceptions` for transport errors. A "use the SDK" policy alone leaks `requests` exceptions into the domain.
- **`openai`** SDK's exceptions changed shape across major versions; pinning the SDK is brittle.
- **`kubernetes`** SDK uses `urllib3` exceptions for some failures; the model classes (`V1Deployment`) are massive auto-generated objects that are tedious to use in unit tests.

The ACL gives us:

1. **A single place** to update when an SDK changes.
2. **A small surface area** for tests to mock.
3. **A consistent error model** for the rest of the codebase.

## Implementation checklist

For every new external integration:

- [ ] Identify the foreign types you must touch.
- [ ] Define a domain port (`Protocol`) with methods that take and return only domain types.
- [ ] Implement an `Adapter` class behind the port.
- [ ] Map every foreign exception to a domain exception (or convert to a fallback signal).
- [ ] Add an integration test that pins the foreign behaviour at the boundary.
- [ ] Add a unit test that asserts no foreign type appears in the public signatures of any non-adapter module.

The last bullet can be enforced with a small AST lint that scans `agent/domain/` and `agent/application/` for imports from `github`, `openai`, `kubernetes`, `requests`, etc., and fails the build if any are found.
