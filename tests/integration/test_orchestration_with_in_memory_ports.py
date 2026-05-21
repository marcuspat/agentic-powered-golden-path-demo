"""Integration test for ``OnboardingOrchestrationService`` with in-memory ports.

Per DDD doc 12 §Step-5, the orchestration test "substitutes in-memory
implementations of every port; runs in <100 ms". This file does exactly
that. No GitHub, no OpenRouter, no kubectl.
"""

from __future__ import annotations

from pathlib import Path

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
orchestration_mod = pytest.importorskip(
    "agent.domain.services.orchestration",
    reason="agent.domain.services.orchestration not yet landed",
)
intent_extraction_mod = pytest.importorskip(
    "agent.domain.services.intent_extraction",
    reason="agent.domain.services.intent_extraction not yet landed",
)
template_rendering_mod = pytest.importorskip(
    "agent.domain.services.template_rendering",
    reason="agent.domain.services.template_rendering not yet landed",
)
source_repo_mod = pytest.importorskip(
    "agent.domain.aggregates.source_repository",
    reason="agent.domain.aggregates.source_repository not yet landed",
)
gitops_repo_mod = pytest.importorskip(
    "agent.domain.aggregates.gitops_repository",
    reason="agent.domain.aggregates.gitops_repository not yet landed",
)
argo_app_mod = pytest.importorskip(
    "agent.domain.aggregates.argo_application",
    reason="agent.domain.aggregates.argo_application not yet landed",
)
stack_mod = pytest.importorskip(
    "agent.domain.aggregates.stack",
    reason="agent.domain.aggregates.stack not yet landed",
)

AppName = values.AppName
AppDescription = values.AppDescription
CommitMessage = values.CommitMessage
GitSha = values.GitSha
Namespace = values.Namespace
OnboardingRequest = values.OnboardingRequest
RepoStatus = values.RepoStatus
RepositoryUrl = values.RepositoryUrl
StackName = values.StackName
StackVersion = values.StackVersion
TemplatePath = values.TemplatePath
TemplateVariableSet = values.TemplateVariableSet
OutcomeKind = values.OutcomeKind

OnboardingOrchestrationService = orchestration_mod.OnboardingOrchestrationService
IntentExtractionService = intent_extraction_mod.IntentExtractionService
TemplateRenderingService = template_rendering_mod.TemplateRenderingService
SourceRepository = source_repo_mod.SourceRepository
GitOpsRepository = gitops_repo_mod.GitOpsRepository
Stack = stack_mod.Stack
SourceTemplate = stack_mod.SourceTemplate
GitOpsTemplate = stack_mod.GitOpsTemplate

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# In-memory port doubles
# ---------------------------------------------------------------------------


class _InMemoryStackRepo:
    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def get(self, name: StackName) -> Stack:  # type: ignore[name-defined]
        return self._stack

    def list_all(self) -> list:
        return [self._stack]


class _InMemorySourceRepoPort:
    def __init__(self) -> None:
        self.created: list = []
        self.populated: list = []

    def create(self, app_name: AppName, description: AppDescription) -> SourceRepository:
        url = RepositoryUrl.from_app(app_name, "source", "test-owner")
        repo = SourceRepository.newly_created(app_name=app_name, url=url)
        self.created.append(repo)
        return repo

    def populate(
        self, repo: SourceRepository, files: list, message: CommitMessage
    ) -> GitSha:
        sha = GitSha("a" * 40)
        repo.mark_populated(message, sha)
        self.populated.append((repo, files, message))
        return sha


class _InMemoryGitOpsRepoPort:
    def __init__(self) -> None:
        self.created: list = []
        self.populated: list = []

    def create(self, app_name: AppName, description: AppDescription) -> GitOpsRepository:
        url = RepositoryUrl.from_app(app_name, "gitops", "test-owner")
        repo = GitOpsRepository.newly_created(
            app_name=app_name,
            url=url,
            namespace=Namespace.from_app(app_name),
        )
        self.created.append(repo)
        return repo

    def populate(
        self, repo: GitOpsRepository, files: list, message: CommitMessage
    ) -> GitSha:
        sha = GitSha("b" * 40)
        repo.status = RepoStatus.POPULATED
        repo.initial_commit = message
        repo.initial_sha = sha
        self.populated.append((repo, files, message))
        return sha


class _InMemoryArgoRepoPort:
    def __init__(self) -> None:
        self.registered: list = []

    def register(self, app) -> None:
        self.registered.append(app)

    def get(self, app_name: AppName):  # noqa: ARG002
        return None


class _RecordingEmitter:
    def __init__(self) -> None:
        self.events: list = []

    def emit(self, envelope) -> None:
        self.events.append(envelope)


# ---------------------------------------------------------------------------
# Tiny in-memory templates the orchestration can render
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_stack(tmp_workspace: Path) -> Stack:
    src = tmp_workspace / "src-template"
    gitops = tmp_workspace / "gitops-template"
    src.mkdir()
    gitops.mkdir()

    # A trivial template that uses just `appName` from the variables bag.
    (src / "README.md").write_text("# {{ appName }}\n")
    (src / "package.json").write_text('{"name": "{{ appName }}"}\n')

    (gitops / "app.yaml").write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: {{ appName }}\n"
    )

    return Stack.of(
        name="nodejs",
        version="0.1.0",
        source_template_dir=src,
        gitops_template_dir=gitops,
        declared_variables={"appName", "description", "namespace", "host", "replicas"},
    )


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------


def test_orchestration_runs_through_with_in_memory_ports(
    in_memory_stack: Stack,
) -> None:
    extractor = IntentExtractionService(llm=None)
    stacks = _InMemoryStackRepo(in_memory_stack)
    renderer = TemplateRenderingService()
    src = _InMemorySourceRepoPort()
    gitops = _InMemoryGitOpsRepoPort()
    argo = _InMemoryArgoRepoPort()
    events = _RecordingEmitter()

    orchestration = OnboardingOrchestrationService(
        intent_extraction=extractor,
        stacks=stacks,
        template_renderer=renderer,
        source_repo=src,
        gitops_repo=gitops,
        argo_repo=argo,
        events=events,
    )

    run = orchestration.run(OnboardingRequest("Please onboard a service called demo-app"))

    # Every port was visited at least once
    assert src.created, "source repo was never created"
    assert src.populated, "source repo was never populated"
    assert gitops.created, "gitops repo was never created"
    assert gitops.populated, "gitops repo was never populated"
    assert argo.registered, "argo application was never registered"
    assert events.events, "orchestration emitted no events"

    # Result carries the canonical app name and a successful outcome
    assert run.extracted_app_name == AppName("demo-app")
    assert run.outcome is not None
    assert run.outcome.kind is OutcomeKind.SUCCEEDED
