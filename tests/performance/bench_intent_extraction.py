"""Micro-benchmark for the regex fallback path of ``IntentExtractionService``.

Asserts only on regressions: a single-extraction call must complete in
under a generous wall-clock budget. Absolute numbers are not asserted on.

Uses ``pytest-benchmark`` if available, else falls back to ``timeit``.
"""

from __future__ import annotations

import timeit
from statistics import mean

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
intent_extraction_mod = pytest.importorskip(
    "agent.domain.services.intent_extraction",
    reason="agent.domain.services.intent_extraction not yet landed",
)
IntentExtractionService = intent_extraction_mod.IntentExtractionService

pytestmark = pytest.mark.performance


_REQUEST = "Please onboard a new microservice called inventory-api with default config."

# Generous wall-clock budget; we only care about catastrophic regressions.
_BUDGET_SECONDS = 0.05


class _NullLlm:
    def extract(self, _request: str) -> object | None:
        return None


def _extract_once() -> None:
    IntentExtractionService(llm=_NullLlm()).extract(_REQUEST)


def test_intent_extraction_regex_under_budget(benchmark=None) -> None:
    """Run via ``pytest-benchmark`` if installed; else use ``timeit``."""
    if benchmark is not None:
        result = benchmark(_extract_once)
        # ``benchmark`` returns the function's return value; we assert via stats.
        stats = getattr(benchmark, "stats", None)
        if stats is not None:
            mean_seconds = stats.stats.mean  # type: ignore[attr-defined]
            assert mean_seconds < _BUDGET_SECONDS, (
                f"intent extraction regressed: {mean_seconds:.4f}s > {_BUDGET_SECONDS}s"
            )
        return result

    # Fallback: timeit
    timings = timeit.repeat(_extract_once, number=10, repeat=5)
    avg = mean(timings) / 10
    assert avg < _BUDGET_SECONDS, (
        f"intent extraction regressed: {avg:.4f}s > {_BUDGET_SECONDS}s (timeit)"
    )
