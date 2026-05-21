"""Domain ports (Protocols).

Infrastructure adapters implement these. The domain layer programs against
the protocols, never against concrete adapter classes — this is what keeps
ACLs effective and the domain testable in isolation.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from agent.domain.events import EventEnvelope
from agent.domain.values import (
    AppDescription,
    AppName,
    BranchName,
    CommitMessage,
    CorrelationId,
    ExtractedIntent,
    GitSha,
    Namespace,
    OnboardingRequest,
    RenderedFile,
    RepositoryUrl,
    StackName,
    TemplateVariables,
)

if TYPE_CHECKING:
    # Aggregates implement these ports, so importing them at runtime would
    # create a cycle. Under TYPE_CHECKING the forward references resolve for
    # mypy without the runtime import.
    from agent.domain.aggregates.argo_application import ArgoApplication
    from agent.domain.aggregates.gitops_repository import GitOpsRepository
    from agent.domain.aggregates.onboarding_run import OnboardingRun
    from agent.domain.aggregates.source_repository import SourceRepository
    from agent.domain.aggregates.stack import Stack

# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #

class LlmCompletionPort(Protocol):
    """Single chat-completion call against an OpenAI-compatible API."""

    def complete(self, prompt: str, *, max_tokens: int = 50, temperature: float = 0.1) -> str: ...


# --------------------------------------------------------------------------- #
# Stack catalog
# --------------------------------------------------------------------------- #

class StackRepositoryPort(Protocol):
    def get(self, name: StackName) -> Stack: ...
    def list_all(self) -> list[Stack]: ...


class TemplateRendererPort(Protocol):
    def render(
        self,
        template_dir: Path,
        variables: TemplateVariables,
    ) -> list[RenderedFile]: ...


# --------------------------------------------------------------------------- #
# Source code provisioning
# --------------------------------------------------------------------------- #

class SourceRepositoryPort(Protocol):
    def create(self, app_name: AppName, description: AppDescription) -> SourceRepository: ...

    def populate(
        self,
        repo: SourceRepository,
        files: list[RenderedFile],
        message: CommitMessage,
        branch: BranchName = BranchName(),
    ) -> GitSha: ...


# --------------------------------------------------------------------------- #
# GitOps configuration
# --------------------------------------------------------------------------- #

class GitOpsRepositoryPort(Protocol):
    def create(self, app_name: AppName, description: AppDescription) -> GitOpsRepository: ...

    def populate(
        self,
        repo: GitOpsRepository,
        files: list[RenderedFile],
        message: CommitMessage,
        branch: BranchName = BranchName(),
    ) -> GitSha: ...


class GitWorkingCopyPort(Protocol):
    """Lower-level git operations. Used by the GitHub repository adapters."""

    def clone(self, url: RepositoryUrl, into: Path) -> None: ...
    def write_files(self, working_copy_dir: Path, files: list[RenderedFile]) -> None: ...
    def commit_all(self, working_copy_dir: Path, message: CommitMessage) -> GitSha: ...
    def push(self, working_copy_dir: Path, branch: BranchName) -> None: ...
    def revert(self, url: RepositoryUrl, target_sha: GitSha | None, message: CommitMessage) -> tuple[GitSha, GitSha]:
        """Revert ``target_sha`` (or HEAD) on the remote. Returns (reverted_sha, new_head_sha)."""
        ...


# --------------------------------------------------------------------------- #
# Deployment orchestration
# --------------------------------------------------------------------------- #

class ArgoApplicationPort(Protocol):
    def register(self, app: ArgoApplication) -> None: ...
    def get(self, app_name: AppName) -> ArgoApplication | None: ...
    def remove(self, app_name: AppName) -> None: ...


class KubernetesApplyPort(Protocol):
    def apply(self, manifest_yaml: str, *, namespace: Namespace | None = None) -> None: ...


class KubernetesReadPort(Protocol):
    def get_json(self, resource: str, name: str, *, namespace: Namespace | None = None) -> dict: ...
    def delete(self, resource: str, name: str, *, namespace: Namespace | None = None, ignore_not_found: bool = True) -> None: ...


class ArgoApplicationProjectionPort(Protocol):
    """Read-only projection of a live ArgoCD Application's status.

    Translates raw ArgoCD CR status fields through the BC-5 ACL into
    domain ``SyncStatus`` / ``HealthStatus`` enums.
    """

    def project(self, app_name: AppName) -> ArgoApplication | None: ...


# --------------------------------------------------------------------------- #
# Run history
# --------------------------------------------------------------------------- #

class OnboardingRunRepositoryPort(Protocol):
    def add(self, run: OnboardingRun) -> None: ...
    def get(self, correlation_id: CorrelationId) -> OnboardingRun | None: ...


# --------------------------------------------------------------------------- #
# Events
# --------------------------------------------------------------------------- #

class EventEmitterPort(Protocol):
    def emit(self, envelope: EventEnvelope) -> None: ...


# --------------------------------------------------------------------------- #
# Intent
# --------------------------------------------------------------------------- #

class IntentExtractionPort(Protocol):
    def extract(self, request: OnboardingRequest) -> ExtractedIntent: ...
