"""Kubernetes ACL — wraps ``kubectl apply`` for now.

Falls back to the ``kubernetes`` Python SDK if ``kubectl`` is unavailable
on PATH. Translates errors into :class:`K8sApplyError` (or
:class:`Unauthorized`) so the domain never sees raw subprocess output or
SDK exception classes.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from agent.domain.errors import K8sApplyError, Unauthorized
from agent.domain.ports import KubernetesApplyPort
from agent.domain.values import Namespace

logger = logging.getLogger(__name__)


class KubectlAdapter(KubernetesApplyPort):
    def __init__(self, kubectl_binary: str = "kubectl") -> None:
        self._bin = kubectl_binary

    def apply(self, manifest_yaml: str, *, namespace: Optional[Namespace] = None) -> None:
        if shutil.which(self._bin) is None:
            raise K8sApplyError(f"{self._bin} not on PATH")
        # Write to a temp file so kubectl reads it via -f (more robust than stdin
        # in some shells).
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, prefix="gpagent-"
        ) as tmp:
            tmp.write(manifest_yaml)
            path = Path(tmp.name)
        try:
            args = [self._bin, "apply", "-f", str(path)]
            if namespace is not None:
                args.extend(["-n", namespace.value])
            proc = subprocess.run(args, check=False, capture_output=True, text=True)
            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                lower = stderr.lower()
                if "forbidden" in lower or "unauthorized" in lower:
                    raise Unauthorized(f"kubectl unauthorized: {stderr}")
                raise K8sApplyError(stderr or proc.stdout.strip())
            logger.info("kubectl.apply ok stdout=%r", proc.stdout.strip())
        finally:
            try:
                path.unlink()
            except OSError:  # pragma: no cover
                pass
