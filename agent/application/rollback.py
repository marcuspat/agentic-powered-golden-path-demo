"""RollbackApplicationService — git revert against a GitOps repository.

See ADR-0019 and ``docs/ddd/10-application-services.md``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from agent.domain.errors import DomainError
from agent.domain.events import EventEnvelope, GitOpsRepositoryRolledBack
from agent.domain.ports import EventEmitterPort, GitWorkingCopyPort
from agent.domain.values import (
    ActorIdentity,
    AppName,
    CommitMessage,
    CorrelationId,
    GitSha,
    Outcome,
    OutcomeKind,
    RepositoryUrl,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RollbackCommand:
    app_name: AppName
    target_sha: Optional[GitSha] = None
    actor: ActorIdentity = ActorIdentity("operator@local")
    reason: str = "operator-initiated rollback"
    gitops_owner: Optional[str] = None  # GitHub user/org


@dataclass(frozen=True)
class RollbackResult:
    app_name: AppName
    new_head_sha: Optional[GitSha]
    reverted_sha: Optional[GitSha]
    outcome: Outcome
    correlation_id: CorrelationId


class RollbackApplicationService:
    def __init__(
        self,
        git: GitWorkingCopyPort,
        events: Optional[EventEmitterPort] = None,
        *,
        default_owner: Optional[str] = None,
    ) -> None:
        self._git = git
        self._events = events
        self._default_owner = default_owner

    def rollback(self, command: RollbackCommand) -> RollbackResult:
        owner = command.gitops_owner or self._default_owner
        if not owner:
            return RollbackResult(
                app_name=command.app_name,
                new_head_sha=None,
                reverted_sha=None,
                outcome=Outcome.failed(
                    "GitHub owner not provided", failed_step="resolve_owner"
                ),
                correlation_id=CorrelationId.new(),
            )
        url = RepositoryUrl.from_app(command.app_name, "gitops", owner)
        message = CommitMessage(
            f"Revert: {command.reason} (rollback by {command.actor.value})"
        )
        try:
            reverted, new_head = self._git.revert(url, command.target_sha, message)
        except DomainError as exc:
            logger.exception("rollback.failed app=%s err=%s", command.app_name, exc)
            return RollbackResult(
                app_name=command.app_name,
                new_head_sha=None,
                reverted_sha=None,
                outcome=Outcome.failed(str(exc), failed_step="git_revert"),
                correlation_id=CorrelationId.new(),
            )
        correlation = CorrelationId.new()
        if self._events is not None:
            self._events.emit(
                EventEnvelope.wrap(
                    GitOpsRepositoryRolledBack(
                        app_name=command.app_name.value,
                        reverted_sha=reverted.value,
                        new_head_sha=new_head.value,
                        operator=command.actor.value,
                    ),
                    correlation_id=correlation,
                    producer="rollback-cli",
                )
            )
        return RollbackResult(
            app_name=command.app_name,
            new_head_sha=new_head,
            reverted_sha=reverted,
            outcome=Outcome.succeeded(),
            correlation_id=correlation,
        )

    @property
    def succeeded(self) -> bool:
        return False  # placeholder; result objects expose the outcome
