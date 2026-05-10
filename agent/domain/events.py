"""Domain events and the common envelope.

See ``docs/ddd/07-domain-events.md`` for the full catalogue and semantics.

Events are dataclasses; the :class:`EventEnvelope` is a sink-agnostic wrapper
that infrastructure adapters can serialise to logs, JSONL files, NATS, Kafka,
or CloudEvents without the domain knowing.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from agent.domain.values import (
    AppName,
    CorrelationId,
    Namespace,
    Outcome,
    OutcomeKind,
    RepositoryUrl,
    Timestamp,
)


# --------------------------------------------------------------------------- #
# Envelope
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class EventEnvelope:
    id: str
    name: str
    version: int
    occurred_at: str
    correlation_id: str
    causation_id: Optional[str]
    producer: str
    payload: dict

    @classmethod
    def wrap(
        cls,
        event: "DomainEvent",
        *,
        correlation_id: CorrelationId,
        producer: str = "agent",
        causation_id: Optional[str] = None,
    ) -> "EventEnvelope":
        return cls(
            id=str(uuid.uuid4()),
            name=event.name,
            version=event.version,
            occurred_at=Timestamp.now().isoformat(),
            correlation_id=correlation_id.value,
            causation_id=causation_id,
            producer=producer,
            payload=event.to_payload(),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=True)


# --------------------------------------------------------------------------- #
# Base
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class DomainEvent:
    """Base for all domain events. Subclasses set ``name`` and ``version``."""

    name: str = field(default="DomainEvent", init=False)
    version: int = field(default=1, init=False)

    def to_payload(self) -> dict:
        # Subclasses may override; the default just turns the dataclass into a dict.
        d = {k: v for k, v in asdict(self).items() if k not in {"name", "version"}}
        # Convert known value-objects to primitives.
        return _coerce_payload(d)


def _coerce_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _coerce_payload(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_payload(v) for v in value]
    if isinstance(value, (AppName, Namespace, RepositoryUrl, CorrelationId)):
        return value.value
    if isinstance(value, OutcomeKind):
        return value.value
    if isinstance(value, Outcome):
        return {
            "kind": value.kind.value,
            "reason": value.reason,
            "failed_step": value.failed_step,
        }
    if isinstance(value, Timestamp):
        return value.isoformat()
    return value


# --------------------------------------------------------------------------- #
# Onboarding events
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class OnboardingRunStarted(DomainEvent):
    name: str = field(default="OnboardingRun.Started", init=False)
    request_text: str = ""
    actor: str = "developer"


@dataclass(frozen=True)
class OnboardingRunIntentExtracted(DomainEvent):
    name: str = field(default="OnboardingRun.IntentExtracted", init=False)
    app_name: str = ""
    stack: str = ""
    extraction_path: str = ""


@dataclass(frozen=True)
class OnboardingRunCompleted(DomainEvent):
    name: str = field(default="OnboardingRun.Completed", init=False)
    app_name: str = ""
    source_repo_url: str = ""
    gitops_repo_url: str = ""
    argo_application_name: str = ""
    namespace: str = ""
    ingress_url: str = ""
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class OnboardingRunFailed(DomainEvent):
    name: str = field(default="OnboardingRun.Failed", init=False)
    app_name: Optional[str] = None
    failed_step: str = "unknown"
    reason: str = ""


# --------------------------------------------------------------------------- #
# Source repository events
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SourceRepositoryCreated(DomainEvent):
    name: str = field(default="SourceRepository.Created", init=False)
    app_name: str = ""
    url: str = ""


@dataclass(frozen=True)
class SourceRepositoryPopulated(DomainEvent):
    name: str = field(default="SourceRepository.Populated", init=False)
    app_name: str = ""
    url: str = ""
    file_count: int = 0
    commit_sha: str = ""
    commit_message: str = ""


# --------------------------------------------------------------------------- #
# GitOps repository events
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class GitOpsRepositoryCreated(DomainEvent):
    name: str = field(default="GitOpsRepository.Created", init=False)
    app_name: str = ""
    url: str = ""


@dataclass(frozen=True)
class GitOpsRepositoryPopulated(DomainEvent):
    name: str = field(default="GitOpsRepository.Populated", init=False)
    app_name: str = ""
    url: str = ""
    namespace: str = ""
    manifest_kinds: list = field(default_factory=list)
    file_count: int = 0
    commit_sha: str = ""


@dataclass(frozen=True)
class GitOpsRepositoryRolledBack(DomainEvent):
    name: str = field(default="GitOpsRepository.RolledBack", init=False)
    app_name: str = ""
    reverted_sha: str = ""
    new_head_sha: str = ""
    operator: str = ""


# --------------------------------------------------------------------------- #
# ArgoCD events (those we emit; ArgoCD-observed events live elsewhere)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ArgoApplicationRegistered(DomainEvent):
    name: str = field(default="ArgoApplication.Registered", init=False)
    app_name: str = ""
    namespace: str = ""
    repo_url: str = ""
    sync_policy: dict = field(default_factory=dict)


__all__ = [
    "ArgoApplicationRegistered",
    "DomainEvent",
    "EventEnvelope",
    "GitOpsRepositoryCreated",
    "GitOpsRepositoryPopulated",
    "GitOpsRepositoryRolledBack",
    "OnboardingRunCompleted",
    "OnboardingRunFailed",
    "OnboardingRunIntentExtracted",
    "OnboardingRunStarted",
    "SourceRepositoryCreated",
    "SourceRepositoryPopulated",
]
