# 12 — Implementation Guide

This document is the **bridge** between the model in docs 01-11 and the executable code in `ai-onboarding-agent/agent.py`. It describes:

1. The **target package layout** that realises the model.
2. A **migration sequence** from today's single-file CLI to that layout.
3. **Code skeletons** for each layer.
4. **Testing patterns** keyed to the tactical constructs.
5. **A reviewer checklist** for ongoing changes.

The intent is that any reasonable Python engineer can read this guide and start writing code that reviewers will accept without lengthy back-and-forth.

## Target package layout

```
agent/
├── __init__.py
├── cli.py                         # transport adapter (argparse, exit codes)
├── application/
│   ├── __init__.py
│   ├── onboarding.py              # OnboardingApplicationService
│   ├── rollback.py                # RollbackApplicationService
│   ├── stack_query.py             # planned
│   └── run_history.py             # planned
├── domain/
│   ├── __init__.py
│   ├── values.py                  # all value objects
│   ├── events.py                  # domain event classes + envelope
│   ├── ports.py                   # repository + service Protocols
│   ├── errors.py                  # domain exception hierarchy
│   ├── aggregates/
│   │   ├── onboarding_run.py
│   │   ├── stack.py
│   │   ├── source_repository.py
│   │   ├── gitops_repository.py
│   │   ├── argo_application.py
│   │   ├── workload.py
│   │   └── observability_profile.py
│   └── services/
│       ├── intent_extraction.py
│       ├── orchestration.py
│       ├── template_rendering.py
│       └── stack_selection.py
├── infrastructure/
│   ├── __init__.py
│   ├── github/
│   │   ├── adapter.py             # PyGithub ACL
│   │   ├── source_repo.py         # SourceRepositoryRepository
│   │   └── gitops_repo.py         # GitOpsRepositoryRepository
│   ├── openrouter/
│   │   └── adapter.py             # OpenRouter ACL
│   ├── git/
│   │   └── adapter.py             # git CLI ACL
│   ├── k8s/
│   │   ├── adapter.py             # kubectl + kubernetes SDK ACL
│   │   ├── argo_repo.py
│   │   └── workload_repo.py
│   ├── catalog/
│   │   └── fs_repo.py             # StackRepository on filesystem
│   ├── runs/
│   │   └── jsonl_repo.py          # OnboardingRunRepository (planned)
│   └── grafana/                   # planned
└── composition.py                 # wire everything; the only place imports cross layers
```

Three rules govern this layout:

1. `agent/domain/` imports **nothing** from `agent/infrastructure/` or `agent/application/`. The domain is self-contained.
2. `agent/application/` imports from `agent/domain/` only. It receives infrastructure implementations through dependency injection.
3. `agent/infrastructure/` imports from `agent/domain/` only — it implements ports defined there.

`agent/composition.py` is the *one* module that imports across all layers. It builds the dependency graph at process start.

## Migration sequence

Migrate in seven small steps, each shippable independently.

### Step 1 — extract value objects

Move sanitisation logic from `extract_app_name_from_request` into a new `agent/domain/values.py` containing `AppName`, `RepositoryUrl`, `Namespace`, `Outcome`, `CorrelationId`, `Timestamp`. Update `agent.py` to use them. No behaviour change, but every test now constructs typed values.

**Acceptance:** `agent.py` no longer contains a slug regex; `tests/unit/test_app_name.py` covers normalisation rules.

### Step 2 — define domain ports

Add `agent/domain/ports.py` with `Protocol` definitions for `SourceRepositoryRepository`, `GitOpsRepositoryRepository`, `ArgoApplicationRepository`, `IntentExtractionService`, `TemplateRenderingService`, etc.

**Acceptance:** ports compile with `mypy --strict`; existing functions in `agent.py` start to depend on the ports rather than concrete classes.

### Step 3 — extract ACLs

Move PyGithub, OpenAI SDK, `git`, and `kubectl` calls into `agent/infrastructure/.../adapter.py`. Each adapter exposes a class implementing one or more domain ports.

**Acceptance:** no `import github`, `import openai`, `import kubernetes`, `subprocess.run(["git", …])`, or `subprocess.run(["kubectl", …])` calls outside `agent/infrastructure/`.

### Step 4 — implement aggregates

Promote `OnboardingRun`, `SourceRepository`, `GitOpsRepository`, `ArgoApplication` to classes in `agent/domain/aggregates/`. Move invariant enforcement (single transition to terminal, namespace-equals-app-name convention, etc.) into the classes.

**Acceptance:** `tests/unit/test_*_aggregate.py` exercises invariants; all flows in `agent.py` use the aggregates.

### Step 5 — domain services

Promote `IntentExtractionService` and a new `OnboardingOrchestrationService` to classes that take ports in their constructor. `run_onboarding_flow()` becomes a one-line wrapper around the orchestration service.

**Acceptance:** the orchestration test (`tests/integration/test_orchestration.py`) substitutes in-memory implementations of every port; runs in <100 ms.

### Step 6 — application service + composition root

Add `agent/application/onboarding.py` (`OnboardingApplicationService`) and `agent/composition.py` (the wiring). `agent/cli.py` becomes a thin argparse wrapper.

**Acceptance:** `python -m agent "..."` works exactly like `python ai-onboarding-agent/agent.py "..."`. The legacy entry point is preserved by `ai-onboarding-agent/agent.py` re-exporting `from agent.cli import main`.

### Step 7 — events

Add `agent/domain/events.py` and an `EventEmitter` port. Adapter implementations: `LoggingEmitter` (default), `JsonlEmitter` (writes `~/.golden-path/events.jsonl`).

**Acceptance:** every step in the orchestration emits a typed event; `tests/unit/test_event_envelope.py` validates schema.

## Code skeletons

### A value object

```python
# agent/domain/values.py
from __future__ import annotations
from dataclasses import dataclass
import re

@dataclass(frozen=True)
class AppName:
    value: str

    _PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")

    def __post_init__(self) -> None:
        if not self._PATTERN.fullmatch(self.value):
            raise ValueError(f"Invalid AppName: {self.value!r}")

    @classmethod
    def from_raw(cls, raw: str) -> AppName:
        s = raw.strip().lower()
        s = re.sub(r"[^a-z0-9-]", "", s)
        s = re.sub(r"-+", "-", s).strip("-")
        if not s:
            raise ValueError("Empty AppName after normalisation")
        return cls(s[:63])

    def __str__(self) -> str:
        return self.value
```

### A domain port

```python
# agent/domain/ports.py
from typing import Protocol
from agent.domain.values import AppName, RepositoryUrl, CommitMessage, GitSha
from agent.domain.aggregates.source_repository import SourceRepository

class SourceRepositoryRepository(Protocol):
    def create(self, app_name: AppName, description: str) -> SourceRepository: ...
    def get(self, app_name: AppName) -> SourceRepository | None: ...
    def populate(
        self,
        repo: SourceRepository,
        files: list[tuple[str, bytes]],
        message: CommitMessage,
    ) -> GitSha: ...
```

### An aggregate

```python
# agent/domain/aggregates/source_repository.py
from dataclasses import dataclass, field
from enum import Enum
from agent.domain.values import AppName, RepositoryUrl, CommitMessage, Timestamp

class RepoStatus(str, Enum):
    EMPTY = "empty"
    POPULATED = "populated"
    FAILED = "failed"

@dataclass
class SourceRepository:
    app_name: AppName
    url: RepositoryUrl
    created_at: Timestamp
    status: RepoStatus = RepoStatus.EMPTY
    initial_commit: CommitMessage | None = None

    def mark_populated(self, message: CommitMessage) -> None:
        if self.status is RepoStatus.POPULATED:
            raise ValueError("SourceRepository already populated")
        if self.status is RepoStatus.FAILED:
            raise ValueError("Cannot populate a failed repository")
        self.status = RepoStatus.POPULATED
        self.initial_commit = message

    def mark_failed(self) -> None:
        self.status = RepoStatus.FAILED
```

### A composition root

```python
# agent/composition.py
import os
from agent.application.onboarding import OnboardingApplicationService
from agent.domain.services.orchestration import OnboardingOrchestrationService
from agent.domain.services.intent_extraction import IntentExtractionService
from agent.domain.services.template_rendering import TemplateRenderingService
from agent.domain.services.stack_selection import StackSelectionService
from agent.infrastructure.github.adapter import PyGithubAdapter
from agent.infrastructure.github.source_repo import GitHubSourceRepoRepository
from agent.infrastructure.github.gitops_repo import GitHubGitOpsRepoRepository
from agent.infrastructure.openrouter.adapter import OpenRouterAdapter
from agent.infrastructure.git.adapter import GitCliAdapter
from agent.infrastructure.k8s.adapter import KubectlAdapter
from agent.infrastructure.k8s.argo_repo import KubernetesArgoApplicationRepository
from agent.infrastructure.catalog.fs_repo import FilesystemStackRepository

def build_onboarding_service() -> OnboardingApplicationService:
    github = PyGithubAdapter(token=os.environ["GITHUB_TOKEN"])
    git = GitCliAdapter()
    kubectl = KubectlAdapter()

    src_repo = GitHubSourceRepoRepository(github, git)
    gitops_repo = GitHubGitOpsRepoRepository(github, git)
    argo_repo = KubernetesArgoApplicationRepository(kubectl)
    stacks = FilesystemStackRepository(root=os.environ.get("STACK_DIR", "cnoe-stacks"))

    extractor = IntentExtractionService(
        llm=OpenRouterAdapter(api_key=os.environ["OPENROUTER_API_KEY"]),
    )
    template_renderer = TemplateRenderingService()
    stack_selector = StackSelectionService(stacks)

    orchestration = OnboardingOrchestrationService(
        extractor=extractor,
        stack_selector=stack_selector,
        template_renderer=template_renderer,
        source_repo=src_repo,
        gitops_repo=gitops_repo,
        argo_repo=argo_repo,
    )

    return OnboardingApplicationService(orchestration)
```

## Testing patterns

| Construct                  | Test pattern                                                            |
|---------------------------|-------------------------------------------------------------------------|
| Value object              | Parametric tests of valid/invalid construction; equality.               |
| Aggregate                 | Drive through state transitions; assert invariants raise.               |
| Domain service            | Inject in-memory port implementations; assert events emitted.           |
| Application service       | Inject the orchestration service stub; verify result mapping.           |
| Adapter (ACL)             | Hit a recorded HTTP cassette / mocked subprocess; assert translations.  |
| Repository (infra)        | Use a real (containerised) backend in `tests/integration/`.             |

For every behaviour test, ask: which layer owns this rule? Then put the test there.

## Compensating actions

Failures partway through an `OnboardingRun` leave artefacts: a created GitHub repo, a populated GitOps repo, a registered ArgoCD App, or any subset. The platform's policy:

1. **Do not auto-clean** — visible failures are preferable to silent partial states; they help operators diagnose.
2. **Always log structured events** — the `OnboardingRun.Failed` event names the failed step so an operator can look up the artefacts.
3. **Provide a `cleanup` CLI** — `python -m agent cleanup <app-name>` deletes the GitHub repos and ArgoCD App. Implementation tracked under follow-up work.

## Reviewer checklist

For any pull request that touches the agent:

- [ ] New nouns added to the **Ubiquitous Language** if they didn't already exist there.
- [ ] No PyGithub / OpenAI / Kubernetes / `subprocess` calls outside `agent/infrastructure/`.
- [ ] New behaviour has a test in the appropriate tier (see ADR-0015).
- [ ] Changes to the public shape of an aggregate or value object have a test for invariants.
- [ ] Cross-context call goes through a port; no shortcut imports.
- [ ] If a new external system is introduced, a new ACL accompanies it.
- [ ] If the change resolves an ADR's "Follow-up Work" item, the checkbox is ticked.
- [ ] If the change supersedes a prior decision, a new ADR exists and the old one is marked `Superseded by ADR-NNNN`.

## What this guide does **not** do

- It does not prescribe a Python framework. The model holds whether you choose `dataclass`, `pydantic`, `attrs`, or pure classes.
- It does not require a specific test runner. `pytest` is the de facto choice; the patterns above translate to `unittest` if needed.
- It does not lock in a future server framework. The application services are framework-agnostic; FastAPI, Litestar, or no server at all all fit.

The model is the durable thing; libraries change.
