"""Micro-benchmark for ``TemplateRenderingService.render``.

Renders the ``cnoe-stacks/nodejs-template`` stack a handful of times and
asserts only on a generous wall-clock budget — see the tier README on why
absolute times are not pinned.
"""

from __future__ import annotations

import timeit
from pathlib import Path
from statistics import mean

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
template_rendering_mod = pytest.importorskip(
    "agent.domain.services.template_rendering",
    reason="agent.domain.services.template_rendering not yet landed",
)
TemplateRenderingService = template_rendering_mod.TemplateRenderingService

pytestmark = pytest.mark.performance


_BUDGET_SECONDS = 0.5  # generous; small templates render in ms.


def _render_once(stack_dir: Path) -> None:
    service = TemplateRenderingService()
    service.render(
        template_dir=stack_dir,
        variables={"appName": "bench-app", "description": "perf bench"},
    )


def test_template_render_under_budget(stack_dir: Path, benchmark=None) -> None:
    nodejs_app = stack_dir / "nodejs-template"
    if not nodejs_app.exists():
        pytest.skip(f"{nodejs_app} not present in this checkout")

    def _go() -> None:
        _render_once(nodejs_app)

    if benchmark is not None:
        benchmark(_go)
        stats = getattr(benchmark, "stats", None)
        if stats is not None:
            mean_seconds = stats.stats.mean  # type: ignore[attr-defined]
            assert mean_seconds < _BUDGET_SECONDS, (
                f"template render regressed: {mean_seconds:.4f}s > {_BUDGET_SECONDS}s"
            )
        return

    timings = timeit.repeat(_go, number=3, repeat=3)
    avg = mean(timings) / 3
    assert avg < _BUDGET_SECONDS, (
        f"template render regressed: {avg:.4f}s > {_BUDGET_SECONDS}s (timeit)"
    )
