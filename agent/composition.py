"""Composition root — the only module that wires layers together.

Every other module imports only from its own layer and from the layer below
it; this module is the seam where infrastructure adapters are bound to the
ports the domain depends on.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from agent.application.onboarding import OnboardingApplicationService
from agent.application.rollback import RollbackApplicationService
from agent.domain.services.intent_extraction import IntentExtractionService
from agent.domain.services.orchestration import OnboardingOrchestrationService
from agent.domain.services.template_rendering import TemplateRenderingService
from agent.infrastructure.catalog.fs_repo import FilesystemStackRepository
from agent.infrastructure.events.emitters import LoggingEmitter
from agent.infrastructure.git.adapter import GitCliAdapter
from agent.infrastructure.github.adapter import PyGithubAdapter
from agent.infrastructure.github.gitops_repo import GitHubGitOpsRepoRepository
from agent.infrastructure.github.source_repo import GitHubSourceRepoRepository
from agent.infrastructure.k8s.adapter import KubectlAdapter
from agent.infrastructure.k8s.argo_repo import KubernetesArgoApplicationRepository
from agent.infrastructure.openrouter.adapter import OpenRouterAdapter

logger = logging.getLogger(__name__)


def _default_stack_root() -> Path:
    explicit = os.environ.get("STACK_DIR")
    if explicit:
        return Path(explicit)
    # Repo-relative default, resolved from this file's location.
    return Path(__file__).resolve().parent.parent / "cnoe-stacks"


def build_onboarding_service(
    *,
    stack_root: Optional[Path] = None,
    enable_llm: bool = True,
) -> OnboardingApplicationService:
    """Wire the production graph and return the application service."""
    github = PyGithubAdapter()
    git = GitCliAdapter()
    kubectl = KubectlAdapter()

    src_repo = GitHubSourceRepoRepository(github, git)
    gitops_repo = GitHubGitOpsRepoRepository(github, git)
    argo_repo = KubernetesArgoApplicationRepository(kubectl)

    stacks = FilesystemStackRepository(stack_root or _default_stack_root())
    renderer = TemplateRenderingService()

    llm = OpenRouterAdapter() if enable_llm else None
    extractor = IntentExtractionService(llm=llm)

    emitter = LoggingEmitter()

    orchestration = OnboardingOrchestrationService(
        intent_extraction=extractor,
        stacks=stacks,
        template_renderer=renderer,
        source_repo=src_repo,
        gitops_repo=gitops_repo,
        argo_repo=argo_repo,
        events=emitter,
    )
    return OnboardingApplicationService(orchestration)


def build_rollback_service(*, default_owner: Optional[str] = None) -> RollbackApplicationService:
    git = GitCliAdapter()
    emitter = LoggingEmitter()
    owner = default_owner or os.environ.get("GITHUB_USERNAME")
    return RollbackApplicationService(git=git, events=emitter, default_owner=owner)
