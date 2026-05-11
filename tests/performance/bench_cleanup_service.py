"""Micro-benchmark for :class:`agent.application.cleanup.CleanupApplicationService`.

The cleanup service is short — three external ops in sequence — but is
hot-path for batch teardowns. We benchmark the in-process orchestration
with all ports replaced by no-ops, to isolate the service's own cost.
"""

from __future__ import annotations

import timeit
from statistics import mean
from typing import Any

import pytest

cleanup_mod = pytest.importorskip(
    "agent.application.cleanup", reason="agent.application.cleanup not yet landed"
)
values_mod = pytest.importorskip(
    "agent.domain.values", reason="agent.domain.values not yet landed"
)

CleanupApplicationService = cleanup_mod.CleanupApplicationService
CleanupCommand = cleanup_mod.CleanupCommand
AppName = values_mod.AppName

pytestmark = pytest.mark.performance


class _NoopArgo:
    def register(self, _app): pass
    def get(self, _name): return None
    def remove(self, _name): pass


class _NoopKubectl:
    def get_json(self, *_a, **_kw): raise NotImplementedError
    def delete(self, *_a, **_kw): pass


_SERVICE = CleanupApplicationService(
    argo_repo=_NoopArgo(),
    kubectl_read=_NoopKubectl(),
    github_owner="acme",
)
_COMMAND = CleanupCommand(app_name=AppName("bench-app"))


def _cleanup_once() -> None:
    _SERVICE.cleanup(_COMMAND)


def test_cleanup_under_budget(benchmark=None) -> None:
    if benchmark is not None:
        benchmark(_cleanup_once)
        return
    runs = 300
    avg = mean(timeit.repeat(_cleanup_once, number=1, repeat=runs))
    assert avg < 0.002, f"cleanup too slow: avg={avg:.6f}s (budget 2ms)"
