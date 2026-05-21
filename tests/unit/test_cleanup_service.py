"""Unit tests for :class:`agent.application.cleanup.CleanupApplicationService`.

Verifies ordering (Argo → namespace → repos), opt-in behaviour for
destructive actions, and that errors in one step do not stop the others.
"""
from __future__ import annotations

import pytest

cleanup_mod = pytest.importorskip(
    "agent.application.cleanup",
    reason="agent.application.cleanup not yet landed",
)
values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed",
)

CleanupApplicationService = cleanup_mod.CleanupApplicationService
CleanupCommand = cleanup_mod.CleanupCommand
AppName = values.AppName
Namespace = values.Namespace

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _FakeArgo:
    def __init__(self, fail: bool = False) -> None:
        self.removed: list[AppName] = []
        self._fail = fail

    def register(self, _app):  # pragma: no cover — not used here
        pass

    def get(self, _name):  # pragma: no cover — not used here
        return None

    def remove(self, name: AppName) -> None:
        if self._fail:
            from agent.domain.errors import K8sApplyError
            raise K8sApplyError("synthetic argo remove failure")
        self.removed.append(name)


class _FakeKubectl:
    def __init__(self, fail_on: str | None = None) -> None:
        self.deleted: list[tuple[str, str, str | None]] = []
        self._fail_on = fail_on

    def get_json(self, *_args, **_kwargs):  # pragma: no cover
        raise NotImplementedError

    def delete(self, resource, name, *, namespace=None, ignore_not_found=True):
        if self._fail_on == resource:
            from agent.domain.errors import K8sApplyError
            raise K8sApplyError(f"synthetic delete failure on {resource}")
        self.deleted.append((resource, name, namespace.value if namespace else None))


class _FakeRepoDeleter:
    def __init__(self, fail_on: str | None = None) -> None:
        self.deleted: list[tuple[str, str]] = []
        self._fail_on = fail_on

    def delete(self, owner: str, name: str) -> None:
        if self._fail_on == name:
            from agent.domain.errors import ExternalSystemError
            raise ExternalSystemError("github", RuntimeError("synthetic"))
        self.deleted.append((owner, name))


class _RecordingEmitter:
    def __init__(self) -> None:
        self.events: list[str] = []

    def emit(self, env) -> None:
        self.events.append(env.name)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_cleanup_removes_argo_then_namespace_skips_repos_by_default() -> None:
    argo = _FakeArgo()
    kubectl = _FakeKubectl()
    events = _RecordingEmitter()
    svc = CleanupApplicationService(
        argo_repo=argo,
        kubectl_read=kubectl,
        repo_deleter=None,
        events=events,
        github_owner="acme",
    )
    result = svc.cleanup(CleanupCommand(app_name=AppName("inventory-api")))
    assert result.succeeded
    assert argo.removed == [AppName("inventory-api")]
    assert kubectl.deleted == [("namespace", "inventory-api", None)]
    assert any("repository_delete" in s for s in result.skipped)
    # Lifecycle events present.
    assert "OnboardedApp.CleanupRequested" in events.events
    assert "OnboardedApp.CleanupCompleted" in events.events


def test_cleanup_deletes_repos_when_opted_in() -> None:
    argo = _FakeArgo()
    kubectl = _FakeKubectl()
    deleter = _FakeRepoDeleter()
    svc = CleanupApplicationService(
        argo_repo=argo, kubectl_read=kubectl, repo_deleter=deleter,
        github_owner="acme",
    )
    result = svc.cleanup(
        CleanupCommand(app_name=AppName("billing"), delete_repos=True)
    )
    assert result.succeeded
    assert deleter.deleted == [
        ("acme", "billing-source"),
        ("acme", "billing-gitops"),
    ]


def test_cleanup_keeps_namespace_when_requested() -> None:
    argo = _FakeArgo()
    kubectl = _FakeKubectl()
    svc = CleanupApplicationService(argo_repo=argo, kubectl_read=kubectl)
    result = svc.cleanup(
        CleanupCommand(app_name=AppName("billing"), keep_namespace=True)
    )
    assert result.succeeded
    assert kubectl.deleted == []
    assert any("keep-namespace" in s for s in result.skipped)


def test_cleanup_overrides_namespace() -> None:
    argo = _FakeArgo()
    kubectl = _FakeKubectl()
    svc = CleanupApplicationService(argo_repo=argo, kubectl_read=kubectl)
    result = svc.cleanup(
        CleanupCommand(app_name=AppName("billing"), namespace=Namespace("legacy-ns"))
    )
    assert result.succeeded
    assert kubectl.deleted == [("namespace", "legacy-ns", None)]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_argo_failure_does_not_block_namespace_cleanup() -> None:
    argo = _FakeArgo(fail=True)
    kubectl = _FakeKubectl()
    svc = CleanupApplicationService(argo_repo=argo, kubectl_read=kubectl)
    result = svc.cleanup(CleanupCommand(app_name=AppName("billing")))
    assert not result.succeeded
    assert any("argo_application_remove" in e for e in result.errors)
    # Namespace step still attempted.
    assert kubectl.deleted == [("namespace", "billing", None)]


def test_namespace_failure_records_error_but_continues() -> None:
    argo = _FakeArgo()
    kubectl = _FakeKubectl(fail_on="namespace")
    deleter = _FakeRepoDeleter()
    svc = CleanupApplicationService(
        argo_repo=argo, kubectl_read=kubectl, repo_deleter=deleter,
        github_owner="acme",
    )
    result = svc.cleanup(
        CleanupCommand(app_name=AppName("billing"), delete_repos=True)
    )
    assert not result.succeeded
    assert any("namespace_delete" in e for e in result.errors)
    # Repo deletion was still attempted.
    assert len(deleter.deleted) == 2


def test_repo_delete_partial_failure_records_specific_repo() -> None:
    argo = _FakeArgo()
    kubectl = _FakeKubectl()
    deleter = _FakeRepoDeleter(fail_on="billing-gitops")
    svc = CleanupApplicationService(
        argo_repo=argo, kubectl_read=kubectl, repo_deleter=deleter,
        github_owner="acme",
    )
    result = svc.cleanup(
        CleanupCommand(app_name=AppName("billing"), delete_repos=True)
    )
    assert not result.succeeded
    assert deleter.deleted == [("acme", "billing-source")]
    assert any("billing-gitops" in e for e in result.errors)


def test_cleanup_without_read_port_skips_namespace_safely() -> None:
    argo = _FakeArgo()
    svc = CleanupApplicationService(argo_repo=argo, kubectl_read=None)
    result = svc.cleanup(CleanupCommand(app_name=AppName("billing")))
    assert result.succeeded
    assert argo.removed == [AppName("billing")]
    assert any("no kubectl read port wired" in s for s in result.skipped)
