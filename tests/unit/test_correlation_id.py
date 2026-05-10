"""Unit tests for the ``CorrelationId`` value object (DDD doc 06, §CorrelationId).

A ``CorrelationId`` wraps a UUIDv4 (as a canonical string). It is generated
at the start of an ``OnboardingRun`` and threaded through logs, events, and
HTTP headers.
"""

from __future__ import annotations

import uuid

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
CorrelationId = values.CorrelationId

pytestmark = pytest.mark.unit


def test_generates_unique_ids() -> None:
    a = CorrelationId.new()
    b = CorrelationId.new()
    assert a != b


def test_accepts_existing_uuid_string() -> None:
    raw = str(uuid.uuid4())
    cid = CorrelationId(raw)
    assert cid.value == raw


def test_string_form_is_canonical_uuid() -> None:
    cid = CorrelationId.new()
    s = str(cid)
    # canonical UUID string length is 36 (8-4-4-4-12 plus four hyphens)
    assert len(s) == 36
    assert s.count("-") == 4


def test_rejects_non_uuid_string() -> None:
    with pytest.raises((ValueError, TypeError, Exception)):
        CorrelationId("not-a-uuid")


def test_value_equality() -> None:
    raw = str(uuid.uuid4())
    assert CorrelationId(raw) == CorrelationId(raw)
