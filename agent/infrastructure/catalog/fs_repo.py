"""Filesystem-backed Stack catalog.

Reads stacks from ``cnoe-stacks/<name>-template/`` and
``cnoe-stacks/<name>-gitops-template/``. If a ``stack.yaml`` is present in
the source-template directory it is honoured; otherwise sensible defaults
are computed from the directory name.
"""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from agent.domain.aggregates.stack import GitOpsTemplate, SourceTemplate, Stack
from agent.domain.errors import StackNotFound
from agent.domain.ports import StackRepositoryPort
from agent.domain.values import (
    StackName,
    StackVersion,
    TemplatePath,
    TemplateVariableSet,
)

logger = logging.getLogger(__name__)

_DEFAULT_VARIABLES = frozenset({"appName", "description", "namespace", "host", "replicas"})


class FilesystemStackRepository(StackRepositoryPort):
    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def get(self, name: StackName) -> Stack:
        src_dir = self._root / f"{name.value}-template"
        gitops_dir = self._root / f"{name.value}-gitops-template"
        # Some stacks store source files under an ``app-source/`` subfolder.
        src_template_dir = src_dir / "app-source" if (src_dir / "app-source").is_dir() else src_dir
        if not src_template_dir.is_dir() or not gitops_dir.is_dir():
            raise StackNotFound(
                f"Stack {name.value!r} not found at {src_template_dir} / {gitops_dir}"
            )
        manifest = _load_stack_yaml(src_dir / "stack.yaml")
        version = StackVersion(manifest.get("version", "0.1.0")) if manifest else StackVersion("0.1.0")
        declared = (
            TemplateVariableSet(frozenset(manifest.get("requiredVariables", []) +
                                          manifest.get("optionalVariables", [])))
            if manifest and (manifest.get("requiredVariables") or manifest.get("optionalVariables"))
            else TemplateVariableSet(_DEFAULT_VARIABLES)
        )
        return Stack(
            name=name,
            version=version,
            declared_variables=declared,
            source_template=SourceTemplate(TemplatePath(src_template_dir)),
            gitops_template=GitOpsTemplate(TemplatePath(gitops_dir)),
        )

    def list_all(self) -> list[Stack]:
        results: list[Stack] = []
        if not self._root.exists():
            return results
        for entry in sorted(self._root.iterdir()):
            if not entry.is_dir():
                continue
            if not entry.name.endswith("-template") or entry.name.endswith("-gitops-template"):
                continue
            base = entry.name[: -len("-template")]
            try:
                results.append(self.get(StackName(base)))
            except StackNotFound:
                continue
        return results


def _load_stack_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            return data
    except yaml.YAMLError as exc:  # pragma: no cover
        logger.warning("stack.yaml parse error path=%s err=%s", path, exc)
    return None
