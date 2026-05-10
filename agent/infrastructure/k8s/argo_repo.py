"""KubernetesArgoApplicationRepository — register Argo Application via kubectl."""
from __future__ import annotations

import logging
from typing import Optional

import yaml

from agent.domain.aggregates.argo_application import ArgoApplication
from agent.domain.ports import ArgoApplicationPort, KubernetesApplyPort
from agent.domain.values import AppName

logger = logging.getLogger(__name__)


class KubernetesArgoApplicationRepository(ArgoApplicationPort):
    def __init__(self, kubectl: KubernetesApplyPort) -> None:
        self._kubectl = kubectl

    def register(self, app: ArgoApplication) -> None:
        manifest = app.to_manifest_dict()
        rendered = yaml.safe_dump(manifest, sort_keys=False)
        logger.info("argo.register name=%s ns=%s", app.name.value, app.destination.namespace.value)
        # ArgoCD Applications live in the argocd namespace. The destination
        # namespace inside the manifest controls workload placement.
        self._kubectl.apply(rendered)

    def get(self, app_name: AppName) -> Optional[ArgoApplication]:  # pragma: no cover — read-back not implemented
        # Reading the live status would require a kubectl get + projection
        # through the BC-5 ACL. Out of scope for this iteration; documented
        # in DDD doc 09.
        return None
