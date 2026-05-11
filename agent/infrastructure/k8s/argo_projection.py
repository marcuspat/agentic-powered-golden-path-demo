"""ArgoApplication ACL — translate ArgoCD CR status to domain types.

Read-only projection from raw ``argoproj.io/v1alpha1 Application`` JSON
(as returned by ``kubectl get application <name> -o json -n argocd``) into
the domain ``ArgoApplication`` aggregate. Centralises the mapping so that,
if ArgoCD ever introduces a new status string, only this module updates.
"""
from __future__ import annotations

import logging
from typing import Optional

from agent.domain.aggregates.argo_application import ArgoApplication
from agent.domain.errors import ExternalSystemError, K8sApplyError, Unauthorized
from agent.domain.ports import ArgoApplicationProjectionPort, KubernetesReadPort
from agent.domain.values import (
    AppName,
    ArgoDestination,
    ArgoProjectName,
    ArgoSource,
    ClusterServer,
    HealthStatus,
    Namespace,
    RepositoryUrl,
    SyncPolicy,
    SyncStatus,
)

logger = logging.getLogger(__name__)


ARGOCD_NAMESPACE = Namespace("argocd")


# Translation tables — the *only* place ArgoCD's vocabulary leaks.
_SYNC_STATUS = {
    "Synced": SyncStatus.SYNCED,
    "OutOfSync": SyncStatus.OUT_OF_SYNC,
}
_HEALTH_STATUS = {
    "Healthy": HealthStatus.HEALTHY,
    "Progressing": HealthStatus.PROGRESSING,
    "Degraded": HealthStatus.DEGRADED,
    "Suspended": HealthStatus.SUSPENDED,
    "Missing": HealthStatus.MISSING,
}


def translate_sync_status(value: object) -> SyncStatus:
    if not isinstance(value, str):
        return SyncStatus.UNKNOWN
    return _SYNC_STATUS.get(value, SyncStatus.UNKNOWN)


def translate_health_status(value: object) -> HealthStatus:
    if not isinstance(value, str):
        return HealthStatus.UNKNOWN
    return _HEALTH_STATUS.get(value, HealthStatus.UNKNOWN)


def project_from_cr(cr: dict) -> ArgoApplication:
    """Pure translation: dict (parsed from kubectl get -o json) → aggregate."""
    if not isinstance(cr, dict):
        raise ExternalSystemError("argocd", TypeError(f"expected dict, got {type(cr).__name__}"))

    metadata = cr.get("metadata") or {}
    spec = cr.get("spec") or {}
    status = cr.get("status") or {}

    name_str = metadata.get("name")
    if not isinstance(name_str, str) or not name_str:
        raise ExternalSystemError(
            "argocd", ValueError("ArgoCD Application CR is missing metadata.name")
        )
    name = AppName(name_str)

    src_spec = spec.get("source") or {}
    repo_url_str = src_spec.get("repoURL", "")
    try:
        repo_url = RepositoryUrl(repo_url_str)
    except ValueError:
        # Accept non-GitHub URLs in projections (e.g. Gitea, mirrored).
        repo_url = RepositoryUrl(_coerce_repo_url(repo_url_str, name))
    source = ArgoSource(
        repo_url=repo_url,
        target_revision=src_spec.get("targetRevision", "HEAD"),
        path=src_spec.get("path", "."),
    )

    dst_spec = spec.get("destination") or {}
    server = ClusterServer(dst_spec.get("server") or "https://kubernetes.default.svc")
    ns_str = dst_spec.get("namespace") or name.value
    destination = ArgoDestination(server=server, namespace=Namespace(ns_str))

    project_name = ArgoProjectName(spec.get("project") or "default")
    sync_policy = _translate_sync_policy(spec.get("syncPolicy") or {})

    sync_status = translate_sync_status((status.get("sync") or {}).get("status"))
    health_status = translate_health_status((status.get("health") or {}).get("status"))

    app = ArgoApplication(
        name=name,
        source=source,
        destination=destination,
        project=project_name,
        sync_policy=sync_policy,
        sync_status=sync_status,
        health_status=health_status,
    )
    return app


def _translate_sync_policy(raw: dict) -> SyncPolicy:
    automated = raw.get("automated") or {}
    sync_options = raw.get("syncOptions") or []
    return SyncPolicy(
        automated=bool(automated),
        prune=bool(automated.get("prune", True)),
        self_heal=bool(automated.get("selfHeal", True)),
        create_namespace=any(
            isinstance(o, str) and o.startswith("CreateNamespace=true") for o in sync_options
        ),
        server_side_apply=any(
            isinstance(o, str) and o.startswith("ServerSideApply=true") for o in sync_options
        ),
    )


def _coerce_repo_url(url: str, name: AppName) -> str:
    """Best-effort canonicalisation of a possibly-non-GitHub URL.

    Used only when projecting a CR whose repoURL is not the canonical GitHub
    form (e.g. local Gitea). Fabricates a syntactically valid HTTPS GitHub
    URL so the aggregate can be constructed without raising; production
    callers should not depend on this fallback.
    """
    if url.endswith(".git"):
        return url if url.startswith("https://github.com/") else f"https://github.com/projected/{name.value}-gitops.git"
    return f"https://github.com/projected/{name.value}-gitops.git"


class KubectlArgoApplicationProjectionService(ArgoApplicationProjectionPort):
    """Read live ArgoCD Application status via kubectl + project to domain."""

    def __init__(self, kubectl: KubernetesReadPort) -> None:
        self._kubectl = kubectl

    def project(self, app_name: AppName) -> Optional[ArgoApplication]:
        try:
            cr = self._kubectl.get_json("application", app_name.value, namespace=ARGOCD_NAMESPACE)
        except K8sApplyError as exc:
            msg = str(exc).lower()
            if "not found" in msg or "notfound" in msg.replace(" ", ""):
                return None
            raise
        except Unauthorized:
            raise
        return project_from_cr(cr)
