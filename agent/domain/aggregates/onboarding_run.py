"""OnboardingRun aggregate.

The conductor's-eye view of one execution of the onboarding workflow.

See ``docs/ddd/05-aggregates-and-entities.md`` §1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agent.domain.values import (
    AppName,
    CorrelationId,
    OnboardingRequest,
    Outcome,
    StackName,
    Timestamp,
)


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class RunPhase(str, Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    TERMINAL = "terminal"


@dataclass
class OnboardingStep:
    name: str
    status: StepStatus = StepStatus.PENDING
    started_at: Timestamp | None = None
    completed_at: Timestamp | None = None
    failure_reason: str | None = None

    def begin(self) -> None:
        if self.status is not StepStatus.PENDING:
            raise ValueError(f"Step {self.name} cannot begin from {self.status}")
        self.status = StepStatus.IN_PROGRESS
        self.started_at = Timestamp.now()

    def succeed(self) -> None:
        if self.status is not StepStatus.IN_PROGRESS:
            raise ValueError(f"Step {self.name} cannot succeed from {self.status}")
        self.status = StepStatus.SUCCEEDED
        self.completed_at = Timestamp.now()

    def fail(self, reason: str) -> None:
        if self.status not in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
            raise ValueError(f"Step {self.name} cannot fail from {self.status}")
        self.status = StepStatus.FAILED
        self.failure_reason = reason
        self.completed_at = Timestamp.now()


@dataclass
class OnboardingRun:
    correlation_id: CorrelationId
    request: OnboardingRequest
    started_at: Timestamp
    extracted_app_name: AppName | None = None
    selected_stack: StackName | None = None
    steps: list[OnboardingStep] = field(default_factory=list)
    outcome: Outcome | None = None
    completed_at: Timestamp | None = None
    source_repo_url: str | None = None
    gitops_repo_url: str | None = None
    namespace: str | None = None

    # ----- factories ----- #

    @classmethod
    def begin(cls, request: OnboardingRequest) -> OnboardingRun:
        return cls(
            correlation_id=CorrelationId.new(),
            request=request,
            started_at=Timestamp.now(),
        )

    # ----- queries ----- #

    @property
    def phase(self) -> RunPhase:
        if self.outcome is not None:
            return RunPhase.TERMINAL
        if self.steps:
            return RunPhase.IN_PROGRESS
        return RunPhase.CREATED

    @property
    def is_terminal(self) -> bool:
        return self.outcome is not None

    @property
    def duration_seconds(self) -> float | None:
        if self.completed_at is None:
            return None
        delta = self.completed_at.value - self.started_at.value
        return delta.total_seconds()

    def find_step(self, name: str) -> OnboardingStep | None:
        return next((s for s in self.steps if s.name == name), None)

    # ----- mutations ----- #

    def record_intent(self, app_name: AppName, stack: StackName) -> None:
        if self.is_terminal:
            raise ValueError("Cannot record intent on a terminal run")
        if self.extracted_app_name is not None:
            raise ValueError("Intent already recorded")
        self.extracted_app_name = app_name
        self.selected_stack = stack

    def begin_step(self, name: str) -> OnboardingStep:
        if self.is_terminal:
            raise ValueError("Cannot begin a step on a terminal run")
        if self.find_step(name) is not None:
            raise ValueError(f"Step {name!r} already exists")
        step = OnboardingStep(name=name)
        step.begin()
        self.steps.append(step)
        return step

    def complete_step(self, name: str) -> None:
        step = self.find_step(name)
        if step is None:
            raise ValueError(f"Unknown step {name!r}")
        step.succeed()

    def fail_step(self, name: str, reason: str) -> None:
        step = self.find_step(name)
        if step is None:
            raise ValueError(f"Unknown step {name!r}")
        step.fail(reason)

    def succeed(self) -> None:
        if self.is_terminal:
            raise ValueError("Run is already terminal")
        if any(s.status is not StepStatus.SUCCEEDED for s in self.steps):
            raise ValueError("Cannot succeed: not all steps are succeeded")
        self.outcome = Outcome.succeeded()
        self.completed_at = Timestamp.now()

    def fail(self, reason: str, failed_step: str) -> None:
        if self.is_terminal:
            raise ValueError("Run is already terminal")
        self.outcome = Outcome.failed(reason=reason, failed_step=failed_step)
        self.completed_at = Timestamp.now()

    def cancel(self, reason: str | None = None) -> None:
        if self.is_terminal:
            raise ValueError("Run is already terminal")
        self.outcome = Outcome.cancelled(reason)
        self.completed_at = Timestamp.now()
