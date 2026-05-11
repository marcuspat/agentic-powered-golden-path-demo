"""Micro-benchmark for the ArgoCD Application status ACL.

The projection is hot-path in any future status-poll loop, so we want a
guard against accidental quadratic translations.

Uses ``pytest-benchmark`` if available; else falls back to ``timeit``.
"""

from __future__ import annotations

import timeit
from statistics import mean

import pytest

projection_mod = pytest.importorskip(
    "agent.infrastructure.k8s.argo_projection",
    reason="agent.infrastructure.k8s.argo_projection not yet landed",
)

project_from_cr = projection_mod.project_from_cr

pytestmark = pytest.mark.performance


_BUDGET_PER_PROJECT_SECONDS = 0.002  # 2 ms — generous for a pure-dict translation


def _sample_cr(name: str = "inventory-api") -> dict:
    return {
        "metadata": {"name": name, "namespace": "argocd"},
        "spec": {
            "project": "default",
            "source": {
                "repoURL": f"https://github.com/acme/{name}-gitops.git",
                "targetRevision": "HEAD",
                "path": ".",
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": name,
            },
            "syncPolicy": {
                "automated": {"prune": True, "selfHeal": True},
                "syncOptions": ["CreateNamespace=true", "ServerSideApply=true"],
            },
        },
        "status": {
            "sync": {"status": "Synced"},
            "health": {"status": "Healthy"},
        },
    }


def test_projection_under_budget(benchmark=None) -> None:
    cr = _sample_cr()

    def _project_once() -> None:
        project_from_cr(cr)

    if benchmark is not None:
        benchmark(_project_once)
        return

    runs = 500
    avg = mean(timeit.repeat(_project_once, number=1, repeat=runs))
    assert avg < _BUDGET_PER_PROJECT_SECONDS, (
        f"argo projection too slow: avg={avg:.6f}s (budget {_BUDGET_PER_PROJECT_SECONDS}s)"
    )


def test_projection_100_apps_in_under_500ms() -> None:
    """Polling 100 apps should never blow a 500 ms budget."""
    crs = [_sample_cr(f"app-{i}") for i in range(100)]
    start = timeit.default_timer()
    for cr in crs:
        project_from_cr(cr)
    elapsed = timeit.default_timer() - start
    assert elapsed < 0.5, f"100 projections took {elapsed:.3f}s (budget 500ms)"
