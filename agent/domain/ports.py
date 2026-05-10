"""Domain ports (Protocols).

Infrastructure adapters implement these. The domain layer programs against
the protocols, never against concrete adapter classes — this is what keeps
ACLs effective and the domain testable in isolation.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, Tuple

from agent.domain.events import DomainEvent, EventEnvelope
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
    def get(self, name: StackName) -> "Stack": ...     # type: ignore[name-defined]
    def list_all(self) -> List["Stack"]: ...           # type: ignore[name-defined]


class TemplateRendererPort(Protocol):
    def render(
        self,
        template_dir,
        variables: TemplateVariables,
    ) -> List[RenderedFile]: ...


# --------------------------------------------------------------------------- #
# Source code provisioning
# --------------------------------------------------------------------------- #

class SourceRepositoryPort(Protocol):
    def create(self, app_name: AppName, description: AppDescription) -> "SourceRepository": ...   # type: ignore[name-defined]

    def populate(
        self,
        repo: "SourceRepository",                                                                  # type: ignore[name-defined]
        files: List[RenderedFile],
        message: CommitMessage,
        branch: BranchName = BranchName(),
    ) -> GitSha: ...


# --------------------------------------------------------------------------- #
# GitOps configuration
# --------------------------------------------------------------------------- #

class GitOpsRepositoryPort(Protocol):
    def create(self, app_name: AppName, description: AppDescription) -> "GitOpsRepository": ...    # type: ignore[name-defined]

    def populate(
        self,
        repo: "GitOpsRepository",                                                                   # type: ignore[name-defined]
        files: List[RenderedFile],
        message: CommitMessage,
        branch: BranchName = BranchName(),
    ) -> GitSha: ...


class GitWorkingCopyPort(Protocol):
    """Lower-level git operations. Used by the GitHub repository adapters."""

    def clone(self, url: RepositoryUrl, into) -> None: ...
    def write_files(self, working_copy_dir, files: List[RenderedFile]) -> None: ...
    def commit_all(self, working_copy_dir, message: CommitMessage) -> GitSha: ...
    def push(self, working_copy_dir, branch: BranchName) -> None: ...
    def revert(self, url: RepositoryUrl, target_sha: Optional[GitSha], message: CommitMessage) -> Tuple[GitSha, GitSha]:
        """Revert ``target_sha`` (or HEAD) on the remote. Returns (reverted_sha, new_head_sha)."""
        ...


# --------------------------------------------------------------------------- #
# Deployment orchestration
# --------------------------------------------------------------------------- #

class ArgoApplicationPort(Protocol):
    def register(self, app: "ArgoApplication") -> None: ...                                         # type: ignore[name-defined]
    def get(self, app_name: AppName) -> Optional["ArgoApplication"]: ...                            # type: ignore[name-defined]


class KubernetesApplyPort(Protocol):
    def apply(self, manifest_yaml: str, *, namespace: Optional[Namespace] = None) -> None: ...


# --------------------------------------------------------------------------- #
# Run history
# --------------------------------------------------------------------------- #

class OnboardingRunRepositoryPort(Protocol):
    def add(self, run: "OnboardingRun") -> None: ...                                                # type: ignore[name-defined]
    def get(self, correlation_id: CorrelationId) -> Optional["OnboardingRun"]: ...                  # type: ignore[name-defined]


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
