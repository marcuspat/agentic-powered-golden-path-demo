"""CleanupApplicationService — tear down an onboarded application.

The agent's onboarding flow does **not** auto-clean on failure (see ADR
follow-up in DDD doc 12 §Compensating actions); operators reach for this
service explicitly via ``python -m agent cleanup <app-name>``.

Order of operations (per "fewest-side-effects-first"):

1. Delete the ArgoCD ``Application`` CR. ArgoCD then prunes the workload.
2. Delete the namespace (best-effort; ArgoCD's prune may have already done
   this if the GitOps manifests defined a Namespace).
3. If ``--repos`` is set, request deletion of the two GitHub repositories.
   Repository deletion is **not** automatic because it is destructive and
   non-reversible; operators must opt in.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from agent.domain.errors import DomainError
from agent.domain.events import EventEnvelope, DomainEvent
from agent.domain.ports import (
    ArgoApplicationPort,
    EventEmitterPort,
    KubernetesReadPort,
)
from agent.domain.values import (
    ActorIdentity,
    AppName,
    CorrelationId,
    Namespace,
    Outcome,
    OutcomeKind,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanupCommand:
    app_name: AppName
    actor: ActorIdentity = ActorIdentity("operator@local")
    delete_repos: bool = False
    keep_namespace: bool = False
    namespace: Optional[Namespace] = None


@dataclass(frozen=True)
class CleanupResult:
    correlation_id: CorrelationId
    app_name: AppName
    outcome: Outcome
    steps_taken: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return self.outcome.kind is OutcomeKind.SUCCEEDED


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OnboardedAppCleanupRequested(DomainEvent):
    name: str = field(default="OnboardedApp.CleanupRequested", init=False)
    app_name: str = ""
    delete_repos: bool = False
    actor: str = ""


@dataclass(frozen=True)
class OnboardedAppCleanupCompleted(DomainEvent):
    name: str = field(default="OnboardedApp.CleanupCompleted", init=False)
    app_name: str = ""
    steps_taken: list = field(default_factory=list)
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Optional port — repository deletion (kept narrow so callers can stub it)
# ---------------------------------------------------------------------------

class RepositoryDeleterPort:
    """Optional port: delete a GitHub repository by ``<owner>/<name>``."""

    def delete(self, owner: str, name: str) -> None:  # pragma: no cover — Protocol-style
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class CleanupApplicationService:
    def __init__(
        self,
        argo_repo: ArgoApplicationPort,
        kubectl_read: Optional[KubernetesReadPort] = None,
        repo_deleter: Optional[RepositoryDeleterPort] = None,
        events: Optional[EventEmitterPort] = None,
        *,
        github_owner: Optional[str] = None,
    ) -> None:
        self._argo = argo_repo
        self._kubectl = kubectl_read
        self._repo_deleter = repo_deleter
        self._events = events
        self._owner = github_owner

    def cleanup(self, command: CleanupCommand) -> CleanupResult:
        correlation = CorrelationId.new()
        steps: List[str] = []
        skipped: List[str] = []
        errors: List[str] = []
        self._emit(
            correlation,
            OnboardedAppCleanupRequested(
                app_name=command.app_name.value,
                delete_repos=command.delete_repos,
                actor=command.actor.value,
            ),
        )

        # 1. Delete the Argo Application CR.
        try:
            self._argo.remove(command.app_name)
            steps.append("argo_application_removed")
        except DomainError as exc:
            errors.append(f"argo_application_remove: {exc}")
            logger.warning("cleanup.argo_remove_failed app=%s err=%s", command.app_name, exc)

        # 2. Delete the namespace.
        if command.keep_namespace:
            skipped.append("namespace_delete (--keep-namespace)")
        elif self._kubectl is None:
            skipped.append("namespace_delete (no kubectl read port wired)")
        else:
            ns = command.namespace or Namespace.from_app(command.app_name)
            try:
                self._kubectl.delete("namespace", ns.value, ignore_not_found=True)
                steps.append(f"namespace_deleted ({ns.value})")
            except DomainError as exc:
                errors.append(f"namespace_delete: {exc}")

        # 3. Optionally delete the two GitHub repos.
        if command.delete_repos:
            if self._repo_deleter is None or not self._owner:
                skipped.append("repository_delete (no deleter or owner)")
            else:
                for kind in ("source", "gitops"):
                    repo_name = f"{command.app_name.value}-{kind}"
                    try:
                        self._repo_deleter.delete(self._owner, repo_name)
                        steps.append(f"repository_deleted ({repo_name})")
                    except DomainError as exc:
                        errors.append(f"repo_delete {repo_name}: {exc}")
        else:
            skipped.append("repository_delete (not requested; pass --repos to opt in)")

        outcome = (
            Outcome.succeeded()
            if not errors
            else Outcome.failed("; ".join(errors), failed_step=steps[-1] if steps else "cleanup")
        )

        self._emit(
            correlation,
            OnboardedAppCleanupCompleted(
                app_name=command.app_name.value,
                steps_taken=list(steps),
                errors=list(errors),
            ),
        )

        return CleanupResult(
            correlation_id=correlation,
            app_name=command.app_name,
            outcome=outcome,
            steps_taken=steps,
            skipped=skipped,
            errors=errors,
        )

    # ----- helpers ----- #

    def _emit(self, correlation: CorrelationId, event: DomainEvent) -> None:
        if self._events is None:
            return
        try:
            self._events.emit(
                EventEnvelope.wrap(
                    event, correlation_id=correlation, producer="cleanup-cli"
                )
            )
        except Exception:  # pragma: no cover — emitter must never break cleanup
            logger.exception("event.emit_failed name=%s", event.name)
