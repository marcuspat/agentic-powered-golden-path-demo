"""Integration test for ``OnboardingApplicationService``.

The application service is a thin coordinator that delegates to the
orchestration service and maps its output to a transport-friendly
``OnboardingResult`` (per DDD doc 12 §Step-6 and ``docs/ddd/10-application-services.md``).
"""

from __future__ import annotations

from typing import Any

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
onboarding_app = pytest.importorskip(
    "agent.application.onboarding",
    reason="agent.application.onboarding not yet landed by orchestrator slice",
)
run_aggregate = pytest.importorskip(
    "agent.domain.aggregates.onboarding_run",
    reason="agent.domain.aggregates.onboarding_run not yet landed",
)

OnboardingApplicationService = onboarding_app.OnboardingApplicationService
OnboardingCommand = onboarding_app.OnboardingCommand
AppName = values.AppName
OnboardingRequest = values.OnboardingRequest
StackName = values.StackName
OnboardingRun = run_aggregate.OnboardingRun

pytestmark = pytest.mark.integration


class _StubOrchestration:
    def __init__(self, app_name: str = "inventory-api") -> None:
        self._app_name = AppName(app_name)
        self.received_request: OnboardingRequest | None = None

    def run(self, request: OnboardingRequest) -> OnboardingRun:
        self.received_request = request
        run = OnboardingRun.begin(request)
        run.record_intent(self._app_name, StackName("nodejs"))
        run.begin_step("extract_intent"); run.complete_step("extract_intent")
        run.source_repo_url = f"https://github.com/acme/{self._app_name.value}-source.git"
        run.gitops_repo_url = f"https://github.com/acme/{self._app_name.value}-gitops.git"
        run.namespace = self._app_name.value
        run.succeed()
        return run


def test_application_service_returns_orchestration_outcome() -> None:
    stub = _StubOrchestration()
    svc = OnboardingApplicationService(stub)

    result = svc.run(OnboardingCommand(request_text="Onboard inventory-api please"))

    assert stub.received_request is not None
    assert stub.received_request.text == "Onboard inventory-api please"
    assert result.succeeded
    assert result.app_name == "inventory-api"
    assert result.namespace == "inventory-api"
    assert result.source_repo_url and "inventory-api-source.git" in result.source_repo_url
    assert result.gitops_repo_url and "inventory-api-gitops.git" in result.gitops_repo_url


def test_application_service_propagates_unexpected_errors_as_failed_outcome() -> None:
    """The application service catches DomainErrors only.

    Generic exceptions like ``RuntimeError`` are *not* caught — they propagate
    so the transport layer (CLI / HTTP) sees them.
    """
    class _BoomOrchestration:
        def run(self, _request: Any) -> Any:
            raise RuntimeError("synthetic failure")

    svc = OnboardingApplicationService(_BoomOrchestration())
    with pytest.raises(RuntimeError, match="synthetic failure"):
        svc.run(OnboardingCommand(request_text="anything"))
