"""TemplateRenderingService — render a Stack's templates with Jinja2.

See ADR-0007 and ``docs/ddd/08-domain-services.md``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import jinja2

from agent.domain.errors import TemplateRenderError
from agent.domain.values import RenderedFile, TemplateVariables

logger = logging.getLogger(__name__)


class TemplateRenderingService:
    """Pure renderer: walks a directory and returns ``[RenderedFile, …]``.

    The caller decides where the bytes land. The service never writes to disk.
    """

    def __init__(self) -> None:
        # ``StrictUndefined`` raises on undeclared variables — surfaces template
        # bugs instead of silently writing ``None``.
        self._env = jinja2.Environment(
            keep_trailing_newline=True,
            autoescape=False,  # we render YAML/JS/Dockerfiles, not HTML
            undefined=jinja2.StrictUndefined,
        )

    def render(self, template_dir, variables) -> List[RenderedFile]:
        root = Path(template_dir)
        if not root.exists():
            raise TemplateRenderError(f"Template directory does not exist: {root}")
        if not root.is_dir():
            raise TemplateRenderError(f"Template path is not a directory: {root}")

        # Accept either a TemplateVariables value object or a plain dict.
        if hasattr(variables, "to_dict"):
            var_dict = variables.to_dict()
        elif isinstance(variables, dict):
            var_dict = dict(variables)
        else:
            raise TemplateRenderError(
                f"variables must be TemplateVariables or dict, got {type(variables).__name__}"
            )
        results: List[RenderedFile] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if _is_skip(path, root):
                continue
            rel = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                # Binary files pass through untouched.
                results.append(RenderedFile(rel, raw))
                continue
            try:
                rendered = self._env.from_string(text).render(**var_dict)
            except jinja2.UndefinedError as exc:
                raise TemplateRenderError(
                    f"Template {rel}: undeclared variable: {exc}"
                ) from exc
            except jinja2.TemplateSyntaxError as exc:
                raise TemplateRenderError(
                    f"Template {rel}:{exc.lineno}: syntax error: {exc.message}"
                ) from exc
            results.append(RenderedFile(rel, rendered.encode("utf-8")))
        logger.info(
            "template.rendered dir=%s files=%d vars=%s",
            root, len(results), sorted(var_dict.keys()),
        )
        return results


_SKIP_BASENAMES = {".git", ".DS_Store", "__pycache__", ".pytest_cache"}


def _is_skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(part in _SKIP_BASENAMES for part in parts)
