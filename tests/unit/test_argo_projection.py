"""Unit tests for the ArgoCD Application status ACL.

The ACL is the *only* place ArgoCD's vocabulary appears outside ArgoCD
itself. New ArgoCD statuses must update :func:`translate_sync_status` or
:func:`translate_health_status`; the rest of the agent only sees the
:class:`SyncStatus` / :class:`HealthStatus` enums.
"""
from __future__ import annotations

import pytest

projection = pytest.importorskip(
    "agent.infrastructure.k8s.argo_projection",
    reason="agent.infrastructure.k8s.argo_projection not yet landed",
)
values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed",
)
argo_aggregate = pytest.importorskip(
    "agent.domain.aggregates.argo_application",
    reason="agent.domain.aggregates.argo_application not yet landed",
)

translate_sync_status = projection.translate_sync_status
translate_health_status = projection.translate_health_status
project_from_cr = projection.project_from_cr
KubectlArgoApplicationProjectionService = projection.KubectlArgoApplicationProjectionService
AppName = values.AppName
SyncStatus = values.SyncStatus
HealthStatus = values.HealthStatus
ArgoApplication = argo_aggregate.ArgoApplication

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Translation tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Synced", SyncStatus.SYNCED),
        ("OutOfSync", SyncStatus.OUT_OF_SYNC),
        ("Unknown", SyncStatus.UNKNOWN),
        ("", SyncStatus.UNKNOWN),
        (None, SyncStatus.UNKNOWN),
        (42, SyncStatus.UNKNOWN),
        ("NotAStatus", SyncStatus.UNKNOWN),
    ],
)
def test_translate_sync_status(raw, expected) -> None:
    assert translate_sync_status(raw) is expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Healthy", HealthStatus.HEALTHY),
        ("Progressing", HealthStatus.PROGRESSING),
        ("Degraded", HealthStatus.DEGRADED),
        ("Suspended", HealthStatus.SUSPENDED),
        ("Missing", HealthStatus.MISSING),
        ("", HealthStatus.UNKNOWN),
        (None, HealthStatus.UNKNOWN),
        ("WeirdNewState", HealthStatus.UNKNOWN),
    ],
)
def test_translate_health_status(raw, expected) -> None:
    assert translate_health_status(raw) is expected


# ---------------------------------------------------------------------------
# project_from_cr
# ---------------------------------------------------------------------------


def _cr(
    *,
    name: str = "inventory-api",
    repo: str = "https://github.com/acme/inventory-api-gitops.git",
    ns: str = "inventory-api",
    sync: str = "Synced",
    health: str = "Healthy",
    target: str = "HEAD",
    path: str = ".",
    project: str = "default",
    automated: bool = True,
    prune: bool = True,
    self_heal: bool = True,
    sync_options: list | None = None,
) -> dict:
    return {
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {
            "project": project,
            "source": {"repoURL": repo, "targetRevision": target, "path": path},
            "destination": {"server": "https://kubernetes.default.svc", "namespace": ns},
            "syncPolicy": {
                "automated": (
                    {"prune": prune, "selfHeal": self_heal} if automated else None
                ),
                "syncOptions": sync_options if sync_options is not None
                else ["CreateNamespace=true", "ServerSideApply=true"],
            },
        },
        "status": {"sync": {"status": sync}, "health": {"status": health}},
    }


def test_project_from_cr_translates_happy_path() -> None:
    app = project_from_cr(_cr())
    assert isinstance(app, ArgoApplication)
    assert app.name == AppName("inventory-api")
    assert app.sync_status is SyncStatus.SYNCED
    assert app.health_status is HealthStatus.HEALTHY
    assert app.destination.namespace.value == "inventory-api"
    assert app.source.repo_url.value == "https://github.com/acme/inventory-api-gitops.git"
    assert app.source.target_revision == "HEAD"
    assert app.source.path == "."
    assert app.project.value == "default"
    assert app.sync_policy.automated is True
    assert app.sync_policy.create_namespace is True
    assert app.sync_policy.server_side_apply is True


def test_project_from_cr_handles_missing_status() -> None:
    cr = _cr()
    cr["status"] = {}
    app = project_from_cr(cr)
    assert app.sync_status is SyncStatus.UNKNOWN
    assert app.health_status is HealthStatus.UNKNOWN


def test_project_from_cr_handles_missing_sync_policy() -> None:
    cr = _cr(automated=False)
    cr["spec"]["syncPolicy"] = {}
    app = project_from_cr(cr)
    assert app.sync_policy.automated is False


def test_project_from_cr_rejects_missing_name() -> None:
    cr = _cr()
    del cr["metadata"]["name"]
    with pytest.raises(Exception):
        project_from_cr(cr)


def test_project_from_cr_tolerates_non_github_repo_url() -> None:
    # Gitea or a local mirror — repoURL not in GitHub canonical form.
    app = project_from_cr(_cr(repo="https://gitea.cnoe.localtest.me/me/inventory-api-gitops.git"))
    # The ACL fabricates a placeholder so the aggregate constructs without
    # raising; tests at the BC boundary should not depend on the exact URL.
    assert isinstance(app, ArgoApplication)


# ---------------------------------------------------------------------------
# KubectlArgoApplicationProjectionService
# ---------------------------------------------------------------------------


class _FakeKubectl:
    def __init__(self, response: dict | None, raise_kind: str | None = None) -> None:
        self._response = response
        self._raise_kind = raise_kind
        self.calls: list = []

    def get_json(self, resource, name, *, namespace=None):
        self.calls.append((resource, name, namespace.value if namespace else None))
        if self._raise_kind == "not_found":
            from agent.domain.errors import K8sApplyError
            raise K8sApplyError('Error from server (NotFound): applications.argoproj.io "x" not found')
        if self._raise_kind == "unauthorized":
            from agent.domain.errors import Unauthorized
            raise Unauthorized("forbidden")
        return self._response

    def delete(self, *_args, **_kwargs):  # pragma: no cover — not used here
        pass


def test_projection_service_calls_kubectl_in_argocd_namespace() -> None:
    fake = _FakeKubectl(_cr())
    svc = KubectlArgoApplicationProjectionService(fake)
    app = svc.project(AppName("inventory-api"))
    assert app is not None
    assert fake.calls == [("application", "inventory-api", "argocd")]


def test_projection_service_returns_none_on_not_found() -> None:
    fake = _FakeKubectl(None, raise_kind="not_found")
    svc = KubectlArgoApplicationProjectionService(fake)
    assert svc.project(AppName("inventory-api")) is None


def test_projection_service_propagates_unauthorized() -> None:
    from agent.domain.errors import Unauthorized
    fake = _FakeKubectl(None, raise_kind="unauthorized")
    svc = KubectlArgoApplicationProjectionService(fake)
    with pytest.raises(Unauthorized):
        svc.project(AppName("inventory-api"))
