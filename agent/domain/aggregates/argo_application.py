"""ArgoApplication aggregate — BC-5 Deployment Orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

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


@dataclass
class ArgoApplication:
    name: AppName
    source: ArgoSource
    destination: ArgoDestination
    project: ArgoProjectName = field(default_factory=ArgoProjectName)
    sync_policy: SyncPolicy = field(default_factory=SyncPolicy)
    sync_status: SyncStatus = SyncStatus.UNKNOWN
    health_status: HealthStatus = HealthStatus.UNKNOWN

    @classmethod
    def for_app(
        cls,
        app_name: AppName,
        gitops_repo_url: RepositoryUrl,
        namespace: Optional[Namespace] = None,
    ) -> "ArgoApplication":
        ns = namespace or Namespace.from_app(app_name)
        return cls(
            name=app_name,
            source=ArgoSource(repo_url=gitops_repo_url),
            destination=ArgoDestination(server=ClusterServer(), namespace=ns),
        )

    def to_manifest_dict(self) -> dict:
        sync_options = []
        if self.sync_policy.create_namespace:
            sync_options.append("CreateNamespace=true")
        if self.sync_policy.server_side_apply:
            sync_options.append("ServerSideApply=true")

        spec_sync_policy: dict = {}
        if self.sync_policy.automated:
            spec_sync_policy["automated"] = {
                "prune": self.sync_policy.prune,
                "selfHeal": self.sync_policy.self_heal,
            }
        if sync_options:
            spec_sync_policy["syncOptions"] = sync_options

        manifest: dict = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": self.name.value,
                "namespace": "argocd",
                "labels": {
                    "app.kubernetes.io/name": self.name.value,
                    "app.kubernetes.io/managed-by": "golden-path-agent",
                },
            },
            "spec": {
                "project": self.project.value,
                "source": {
                    "repoURL": self.source.repo_url.value,
                    "targetRevision": self.source.target_revision,
                    "path": self.source.path,
                },
                "destination": {
                    "server": self.destination.server.value,
                    "namespace": self.destination.namespace.value,
                },
            },
        }
        if spec_sync_policy:
            manifest["spec"]["syncPolicy"] = spec_sync_policy
        return manifest

    def project_status(self, sync: SyncStatus, health: HealthStatus) -> None:
        self.sync_status = sync
        self.health_status = health
