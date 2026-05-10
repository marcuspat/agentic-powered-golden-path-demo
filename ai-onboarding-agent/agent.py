"""Legacy entry point — preserved for back-compat with ``demo.sh`` and existing tests.

The implementation has moved into the ``agent/`` package per ADR-0013 and the
DDD implementation guide (``docs/ddd/12-implementation-guide.md``). This file
delegates to ``agent.cli.main`` so that the original invocation pattern
``python3 ai-onboarding-agent/agent.py "<request>"`` continues to work.

It also re-exports the legacy free functions (``create_github_repo``,
``populate_repo_from_stack``, ``create_argocd_application``,
``extract_app_name_from_request``, ``run_onboarding_flow``) as thin wrappers
around the new structured services so existing callers and tests keep
working while we migrate.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Make the repo root importable when this script is run directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.application.onboarding import (  # noqa: E402
    OnboardingCommand,
    OnboardingOptions,
)
from agent.cli import main as _cli_main  # noqa: E402
from agent.composition import build_onboarding_service  # noqa: E402
from agent.domain.services.intent_extraction import IntentExtractionService  # noqa: E402
from agent.domain.values import (  # noqa: E402
    ActorIdentity,
    AppDescription,
    AppName,
    OnboardingRequest,
    OutcomeKind,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Back-compat shims (do not remove without updating callers / tests).
# --------------------------------------------------------------------------- #

def extract_app_name_from_request(request: str) -> str:
    """Return the slugified app-name extracted from a free-text request."""
    service = IntentExtractionService()
    intent = service.extract(OnboardingRequest(request))
    return intent.app_name.value


def create_github_repo(app_name: str):
    """Create the source + gitops repos. Returns ``(source_url, gitops_url)``."""
    from agent.infrastructure.github.adapter import PyGithubAdapter

    adapter = PyGithubAdapter()
    name = AppName(app_name)
    description = AppDescription.for_app(name)
    src = adapter.create_repository(name, "source", description.text)
    gitops = adapter.create_repository(name, "gitops", description.text)
    return src.value, gitops.value


def populate_repo_from_stack(repo_url: str, template_path: str, app_name: str,
                             description: str = "") -> bool:
    """Render ``template_path`` and push to ``repo_url``."""
    from agent.domain.services.template_rendering import TemplateRenderingService
    from agent.domain.values import (
        BranchName,
        CommitMessage,
        IngressHost,
        Namespace,
        RepositoryUrl,
        TemplateVariables,
    )
    from agent.infrastructure.git.adapter import GitCliAdapter

    name = AppName(app_name)
    desc = AppDescription(description or AppDescription.for_app(name).text)
    variables = TemplateVariables(
        app_name=name,
        description=desc,
        namespace=Namespace.from_app(name),
        host=IngressHost(f"{name.value}.cnoe.localtest.me"),
    )
    files = TemplateRenderingService().render(template_path, variables)
    git = GitCliAdapter()
    url = RepositoryUrl(repo_url)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="gpagent-shim-") as tmp:
        wc = Path(tmp) / url.repo_name
        git.clone(url, wc)
        git.write_files(wc, files)
        git.commit_all(wc, CommitMessage("Initial commit from Golden Path Agent"))
        git.push(wc, BranchName())
    return True


def create_argocd_application(app_name: str, gitops_repo_url: str) -> bool:
    """Apply the ArgoCD ``Application`` CR for ``app_name``."""
    from agent.domain.aggregates.argo_application import ArgoApplication
    from agent.domain.values import RepositoryUrl
    from agent.infrastructure.k8s.adapter import KubectlAdapter
    from agent.infrastructure.k8s.argo_repo import KubernetesArgoApplicationRepository

    name = AppName(app_name)
    argo = ArgoApplication.for_app(name, RepositoryUrl(gitops_repo_url))
    repo = KubernetesArgoApplicationRepository(KubectlAdapter())
    repo.register(argo)
    return True


def run_onboarding_flow(developer_request: str) -> bool:
    """End-to-end flow. Returns ``True`` on success, ``False`` on failure."""
    service = build_onboarding_service()
    result = service.run(
        OnboardingCommand(
            request_text=developer_request,
            actor=ActorIdentity("legacy-shim"),
            options=OnboardingOptions(),
        )
    )
    return result.outcome.kind is OutcomeKind.SUCCEEDED


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        # Legacy invocation: ``agent.py "<request>"`` — defer to the CLI.
        sys.exit(_cli_main(sys.argv[1:]))
    sys.exit(_cli_main(sys.argv[1:]))
