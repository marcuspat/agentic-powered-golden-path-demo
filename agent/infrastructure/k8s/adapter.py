"""Kubernetes ACL — wraps ``kubectl`` for apply, get, and delete.

Translates errors into :class:`K8sApplyError` (or :class:`Unauthorized`) so
the domain never sees raw subprocess output or SDK exception classes.
"""
from __future__ import annotations

import contextlib
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.domain.errors import K8sApplyError, Unauthorized
from agent.domain.ports import KubernetesApplyPort, KubernetesReadPort
from agent.domain.values import Namespace

logger = logging.getLogger(__name__)


class KubectlAdapter(KubernetesApplyPort, KubernetesReadPort):
    def __init__(self, kubectl_binary: str = "kubectl") -> None:
        self._bin = kubectl_binary

    # ----- apply ----- #

    def apply(self, manifest_yaml: str, *, namespace: Namespace | None = None) -> None:
        self._require_kubectl()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, prefix="gpagent-"
        ) as tmp:
            tmp.write(manifest_yaml)
            path = Path(tmp.name)
        try:
            args = [self._bin, "apply", "-f", str(path)]
            if namespace is not None:
                args.extend(["-n", namespace.value])
            self._run(args, op="apply")
            logger.info("kubectl.apply ok")
        finally:
            with contextlib.suppress(OSError):  # pragma: no cover
                path.unlink()

    # ----- read ----- #

    def get_json(
        self, resource: str, name: str, *, namespace: Namespace | None = None
    ) -> dict:
        self._require_kubectl()
        args = [self._bin, "get", resource, name, "-o", "json"]
        if namespace is not None:
            args.extend(["-n", namespace.value])
        stdout = self._run(args, op="get")
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise K8sApplyError(f"kubectl returned invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise K8sApplyError(f"expected JSON object, got {type(data).__name__}")
        return data

    def delete(
        self,
        resource: str,
        name: str,
        *,
        namespace: Namespace | None = None,
        ignore_not_found: bool = True,
    ) -> None:
        self._require_kubectl()
        args = [self._bin, "delete", resource, name]
        if namespace is not None:
            args.extend(["-n", namespace.value])
        if ignore_not_found:
            args.append("--ignore-not-found=true")
        self._run(args, op="delete")
        logger.info("kubectl.delete ok resource=%s name=%s ns=%s", resource, name, namespace)

    # ----- internals ----- #

    def _require_kubectl(self) -> None:
        if shutil.which(self._bin) is None:
            raise K8sApplyError(f"{self._bin} not on PATH")

    def _run(self, args: list, *, op: str) -> str:
        proc = subprocess.run(args, check=False, capture_output=True, text=True)
        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            lower = stderr.lower()
            if "forbidden" in lower or "unauthorized" in lower or "401" in lower:
                raise Unauthorized(f"kubectl {op} unauthorized: {stderr}")
            if "notfound" in lower.replace(" ", "") and "--ignore-not-found" not in args:
                # Translate a not-found that we didn't suppress into a domain error
                # rather than an apply error.
                raise K8sApplyError(stderr)
            raise K8sApplyError(stderr or proc.stdout.strip())
        return proc.stdout
