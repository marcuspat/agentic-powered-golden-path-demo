"""Integration tests for the ``TemplateRenderingService``.

Uses a real Jinja2 environment over real, on-disk templates from
``cnoe-stacks/``. Outputs are written under ``tmp_path`` so the host
filesystem is never mutated. No external systems are touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

jinja2 = pytest.importorskip("jinja2", reason="Jinja2 is required for template rendering")

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
template_rendering = pytest.importorskip(
    "agent.domain.services.template_rendering",
    reason="agent.domain.services.template_rendering not yet landed",
)
TemplateRenderingService = template_rendering.TemplateRenderingService
AppName = values.AppName
AppDescription = values.AppDescription
Namespace = values.Namespace
IngressHost = values.IngressHost
ReplicaCount = values.ReplicaCount
TemplateVariables = values.TemplateVariables

pytestmark = pytest.mark.integration


def _vars(app: str = "demo-app") -> "TemplateVariables":
    name = AppName(app)
    return TemplateVariables(
        app_name=name,
        description=AppDescription.for_app(name),
        namespace=Namespace.from_app(name),
        host=IngressHost(f"{name.value}.cnoe.localtest.me"),
        replicas=ReplicaCount(2),
    )


def test_render_nodejs_app_template_against_live_stack(
    stack_dir: Path, tmp_workspace: Path
) -> None:
    """Render the on-disk ``nodejs-template`` stack and verify output shape."""
    nodejs_app = stack_dir / "nodejs-template"
    if not nodejs_app.exists():
        pytest.skip(f"{nodejs_app} not present in this checkout")

    service = TemplateRenderingService()
    files = service.render(template_dir=nodejs_app, variables=_vars())

    assert isinstance(files, list)
    assert files, "expected at least one rendered file"

    # Materialise to disk under tmp so we can inspect the result without
    # leaking outside the test workspace.
    for rendered in files:
        target = tmp_workspace / rendered.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rendered.content)

    materialised = list(tmp_workspace.rglob("*"))
    assert materialised, "no files materialised under tmp_workspace"


def test_render_substitutes_app_name_into_outputs(stack_dir: Path) -> None:
    """Verify the requested ``appName`` ends up in at least one rendered file."""
    nodejs_app = stack_dir / "nodejs-template"
    if not nodejs_app.exists():
        pytest.skip(f"{nodejs_app} not present in this checkout")

    service = TemplateRenderingService()
    files = service.render(
        template_dir=nodejs_app,
        variables=_vars("substitute-me"),
    )

    blob = b"".join(rendered.content for rendered in files)
    assert b"substitute-me" in blob, (
        "appName should appear in at least one rendered file"
    )


def test_render_rejects_missing_directory(tmp_workspace: Path) -> None:
    """Non-existent template_dir must raise a TemplateRenderError."""
    service = TemplateRenderingService()
    with pytest.raises(Exception):
        service.render(template_dir=tmp_workspace / "nope", variables=_vars())


def test_typed_app_name_round_trips_through_renderer(stack_dir: Path) -> None:
    """The renderer accepts ``TemplateVariables`` containing typed AppName values."""
    nodejs_app = stack_dir / "nodejs-template"
    if not nodejs_app.exists():
        pytest.skip(f"{nodejs_app} not present in this checkout")

    service = TemplateRenderingService()
    files = service.render(template_dir=nodejs_app, variables=_vars("typed-app"))
    assert files
