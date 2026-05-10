"""OnboardingApplicationService — drives the orchestration from a transport."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from agent.domain.aggregates.onboarding_run import OnboardingRun
from agent.domain.errors import DomainError
from agent.domain.services.orchestration import OnboardingOrchestrationService
from agent.domain.values import (
    ActorIdentity,
    CorrelationId,
    OnboardingRequest,
    Outcome,
    OutcomeKind,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OnboardingOptions:
    dry_run: bool = False
    force_recreate: bool = False


@dataclass(frozen=True)
class OnboardingCommand:
    request_text: str
    actor: ActorIdentity = ActorIdentity("developer@local")
    options: OnboardingOptions = OnboardingOptions()


@dataclass(frozen=True)
class OnboardingResult:
    correlation_id: CorrelationId
    outcome: Outcome
    app_name: Optional[str]
    source_repo_url: Optional[str]
    gitops_repo_url: Optional[str]
    argo_application_name: Optional[str]
    namespace: Optional[str]
    ingress_url: Optional[str]
    duration_seconds: float

    @property
    def succeeded(self) -> bool:
        return self.outcome.kind is OutcomeKind.SUCCEEDED


class OnboardingApplicationService:
    def __init__(self, orchestration: OnboardingOrchestrationService) -> None:
        self._orchestration = orchestration

    def run(self, command: OnboardingCommand) -> OnboardingResult:
        request = OnboardingRequest(command.request_text)
        if command.options.dry_run:
            logger.warning("onboarding.dry_run command=%s", command)
            return OnboardingResult(
                correlation_id=CorrelationId.new(),
                outcome=Outcome.cancelled("dry_run"),
                app_name=None, source_repo_url=None, gitops_repo_url=None,
                argo_application_name=None, namespace=None, ingress_url=None,
                duration_seconds=0.0,
            )
        try:
            run = self._orchestration.run(request)
        except DomainError as exc:
            # Belt-and-braces: orchestration should not raise, but if it does
            # we map to a Failed result rather than propagating.
            logger.exception("onboarding.unexpected_domain_error err=%s", exc)
            return OnboardingResult(
                correlation_id=CorrelationId.new(),
                outcome=Outcome.failed(str(exc), failed_step="application_service"),
                app_name=None, source_repo_url=None, gitops_repo_url=None,
                argo_application_name=None, namespace=None, ingress_url=None,
                duration_seconds=0.0,
            )
        return _to_result(run)


def _to_result(run: OnboardingRun) -> OnboardingResult:
    app_name = run.extracted_app_name.value if run.extracted_app_name else None
    ingress_url = (
        f"http://{app_name}.cnoe.localtest.me" if app_name else None
    )
    return OnboardingResult(
        correlation_id=run.correlation_id,
        outcome=run.outcome or Outcome.failed("Unknown failure", "unknown"),
        app_name=app_name,
        source_repo_url=run.source_repo_url,
        gitops_repo_url=run.gitops_repo_url,
        argo_application_name=app_name,
        namespace=run.namespace,
        ingress_url=ingress_url if (run.outcome and run.outcome.kind is OutcomeKind.SUCCEEDED) else None,
        duration_seconds=run.duration_seconds or 0.0,
    )
