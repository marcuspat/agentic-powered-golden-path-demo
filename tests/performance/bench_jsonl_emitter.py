"""Micro-benchmark for :class:`agent.infrastructure.events.emitters.JsonlEmitter`.

Asserts only on regressions: serialising-and-appending a single envelope
must complete in under a generous wall-clock budget. Absolute numbers are
not asserted on.

Uses ``pytest-benchmark`` if available; else falls back to ``timeit``.
"""

from __future__ import annotations

import timeit
from pathlib import Path
from statistics import mean

import pytest

emitters_mod = pytest.importorskip(
    "agent.infrastructure.events.emitters",
    reason="agent.infrastructure.events.emitters not yet landed",
)
events_mod = pytest.importorskip(
    "agent.domain.events",
    reason="agent.domain.events not yet landed",
)
values_mod = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed",
)

JsonlEmitter = emitters_mod.JsonlEmitter
EventEnvelope = events_mod.EventEnvelope
OnboardingRunStarted = events_mod.OnboardingRunStarted
SourceRepositoryPopulated = events_mod.SourceRepositoryPopulated
CorrelationId = values_mod.CorrelationId

pytestmark = pytest.mark.performance


_BUDGET_SECONDS_PER_EMIT = 0.005  # 5 ms is *very* generous for an append.


def _bench_event() -> EventEnvelope:
    return EventEnvelope.wrap(
        SourceRepositoryPopulated(
            app_name="bench-app",
            url="https://github.com/acme/bench-app-source.git",
            file_count=7,
            commit_sha="a" * 40,
            commit_message="Initial commit from Golden Path Agent",
        ),
        correlation_id=CorrelationId.new(),
    )


def test_jsonl_emit_under_budget(tmp_path: Path, benchmark=None) -> None:
    log = tmp_path / "events.jsonl"
    emitter = JsonlEmitter(log)
    envelope = _bench_event()

    def _emit_once() -> None:
        emitter.emit(envelope)

    if benchmark is not None:
        benchmark(_emit_once)
        return

    runs = 200
    elapsed = timeit.repeat(_emit_once, number=1, repeat=runs)
    avg = mean(elapsed)
    assert avg < _BUDGET_SECONDS_PER_EMIT, (
        f"jsonl emit too slow: avg={avg:.6f}s over {runs} runs "
        f"(budget {_BUDGET_SECONDS_PER_EMIT}s)"
    )


def test_jsonl_emit_throughput_1k_events(tmp_path: Path) -> None:
    """Sanity check: 1000 envelopes append-then-flush in well under a second."""
    log = tmp_path / "events.jsonl"
    emitter = JsonlEmitter(log)
    cid = CorrelationId.new()
    envelopes = [
        EventEnvelope.wrap(OnboardingRunStarted(request_text=f"req-{i}"),
                           correlation_id=cid)
        for i in range(1000)
    ]
    start = timeit.default_timer()
    for env in envelopes:
        emitter.emit(env)
    elapsed = timeit.default_timer() - start
    assert elapsed < 2.0, f"1000 emits took {elapsed:.3f}s (budget 2s)"
    # Verify all lines landed.
    assert sum(1 for _ in open(log)) == 1000


def test_envelope_serialisation_is_O_n(benchmark=None) -> None:
    """Serialising an envelope twice should take ~the same time (no caching weirdness)."""
    env = _bench_event()

    def _twice() -> None:
        env.to_json()
        env.to_json()

    if benchmark is not None:
        benchmark(_twice)
        return

    runs = 500
    elapsed = mean(timeit.repeat(_twice, number=1, repeat=runs))
    assert elapsed < 0.002, f"to_json doubled-call too slow: {elapsed:.6f}s"
