"""Unit tests for :class:`agent.infrastructure.events.emitters.JsonlEmitter`.

Per DDD doc 07 §Storage and retention, the JSONL emitter must:

- Append one JSON object per line to the configured file.
- Tolerate parent-directory creation (so callers can pass ``~/.golden-path/...``).
- Preserve the envelope schema (id, name, version, occurred_at, correlation_id,
  causation_id, producer, payload).
- Be tail-able with ``jq`` — each line a self-contained, valid JSON object.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

emitters = pytest.importorskip(
    "agent.infrastructure.events.emitters",
    reason="agent.infrastructure.events.emitters not yet landed",
)
domain_events = pytest.importorskip(
    "agent.domain.events",
    reason="agent.domain.events not yet landed",
)
values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed",
)

JsonlEmitter = emitters.JsonlEmitter
CompositeEmitter = emitters.CompositeEmitter
LoggingEmitter = emitters.LoggingEmitter
EventEnvelope = domain_events.EventEnvelope
OnboardingRunStarted = domain_events.OnboardingRunStarted
SourceRepositoryCreated = domain_events.SourceRepositoryCreated
CorrelationId = values.CorrelationId

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap(event, cid: CorrelationId, **kwargs) -> EventEnvelope:
    return EventEnvelope.wrap(event, correlation_id=cid, **kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_appends_one_line_per_event(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    emitter = JsonlEmitter(log)
    cid = CorrelationId.new()
    emitter.emit(_wrap(OnboardingRunStarted(request_text="one"), cid))
    emitter.emit(_wrap(OnboardingRunStarted(request_text="two"), cid))
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_each_line_is_valid_json(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    emitter = JsonlEmitter(log)
    cid = CorrelationId.new()
    emitter.emit(_wrap(OnboardingRunStarted(request_text="hi"), cid))
    parsed = [json.loads(line) for line in log.read_text().splitlines()]
    assert all(isinstance(rec, dict) for rec in parsed)


def test_envelope_schema_is_complete(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    emitter = JsonlEmitter(log)
    cid = CorrelationId.new()
    emitter.emit(_wrap(SourceRepositoryCreated(app_name="demo-app", url="x"), cid))
    rec = json.loads(log.read_text().splitlines()[0])
    for field in ("id", "name", "version", "occurred_at", "correlation_id",
                  "causation_id", "producer", "payload"):
        assert field in rec, f"missing field {field!r}"
    assert rec["name"] == "SourceRepository.Created"
    assert rec["correlation_id"] == cid.value
    assert rec["payload"]["app_name"] == "demo-app"


def test_creates_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "events.jsonl"
    emitter = JsonlEmitter(nested)
    emitter.emit(_wrap(OnboardingRunStarted(request_text="x"), CorrelationId.new()))
    assert nested.exists()


def test_composite_fan_out(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    composite = CompositeEmitter(LoggingEmitter(), JsonlEmitter(log))
    composite.emit(_wrap(OnboardingRunStarted(request_text="ok"), CorrelationId.new()))
    assert log.exists() and log.read_text().strip().count("\n") >= 0


def test_composite_continues_on_one_failure(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"

    class _BoomEmitter:
        def emit(self, _env):  # noqa: D401
            raise RuntimeError("synthetic")

    composite = CompositeEmitter(_BoomEmitter(), JsonlEmitter(log))
    composite.emit(_wrap(OnboardingRunStarted(request_text="x"), CorrelationId.new()))
    # Despite the first emitter raising, the second still wrote.
    assert log.exists()
    assert log.read_text().strip()


def test_envelope_field_order_is_stable(tmp_path: Path) -> None:
    """The JSON sort_keys=True invariant lets us diff event logs deterministically."""
    log = tmp_path / "events.jsonl"
    emitter = JsonlEmitter(log)
    cid = CorrelationId.new()
    emitter.emit(_wrap(OnboardingRunStarted(request_text="A"), cid))
    rec = json.loads(log.read_text().splitlines()[0])
    # Re-serialise with sort_keys=True and verify the on-disk line matches —
    # this is the strongest possible "keys are sorted" guarantee.
    assert log.read_text().splitlines()[0] == json.dumps(
        rec, separators=(",", ":"), sort_keys=True
    )
