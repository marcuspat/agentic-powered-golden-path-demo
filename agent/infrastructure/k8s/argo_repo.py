"""KubernetesArgoApplicationRepository.

Combines:

- ``KubernetesApplyPort.apply`` for ``register`` (write).
- ``KubernetesReadPort.get_json`` + projection ACL for ``get`` (read).
- ``KubernetesReadPort.delete`` for ``remove``.
"""
from __future__ import annotations

import logging

import yaml

from agent.domain.aggregates.argo_application import ArgoApplication
from agent.domain.ports import (
    ArgoApplicationPort,
    KubernetesApplyPort,
    KubernetesReadPort,
)
from agent.domain.values import AppName
from agent.infrastructure.k8s.argo_projection import (
    ARGOCD_NAMESPACE,
    KubectlArgoApplicationProjectionService,
)

logger = logging.getLogger(__name__)


class KubernetesArgoApplicationRepository(ArgoApplicationPort):
    def __init__(
        self,
        kubectl_apply: KubernetesApplyPort,
        kubectl_read: KubernetesReadPort | None = None,
    ) -> None:
        self._apply = kubectl_apply
        # The read port is optional so legacy call sites still work; if it is
        # not provided, get() returns None and remove() is a no-op.
        self._read = kubectl_read
        self._projection = (
            KubectlArgoApplicationProjectionService(kubectl_read)
            if kubectl_read is not None
            else None
        )

    def register(self, app: ArgoApplication) -> None:
        manifest = app.to_manifest_dict()
        rendered = yaml.safe_dump(manifest, sort_keys=False)
        logger.info(
            "argo.register name=%s ns=%s", app.name.value, app.destination.namespace.value
        )
        self._apply.apply(rendered)

    def get(self, app_name: AppName) -> ArgoApplication | None:
        if self._projection is None:
            return None
        return self._projection.project(app_name)

    def remove(self, app_name: AppName) -> None:
        if self._read is None:
            logger.warning("argo.remove skipped (no read port wired) name=%s", app_name.value)
            return
        self._read.delete(
            "application", app_name.value, namespace=ARGOCD_NAMESPACE, ignore_not_found=True
        )
        logger.info("argo.remove ok name=%s", app_name.value)
