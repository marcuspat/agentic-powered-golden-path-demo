"""Unit tests for the ``Timestamp`` value object (DDD doc 06, §Timestamp).

Always UTC. Always ISO-8601 in serialised form. Never naive ``datetime``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
Timestamp = values.Timestamp

pytestmark = pytest.mark.unit


def test_now_is_utc_aware() -> None:
    ts = Timestamp.now()
    assert ts.value.tzinfo is not None
    assert ts.value.utcoffset() == timedelta(0)


def test_explicit_aware_datetime_accepted() -> None:
    moment = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    ts = Timestamp(moment)
    assert ts.value == moment


def test_naive_datetime_rejected() -> None:
    naive = datetime(2026, 5, 10, 12, 0, 0)
    with pytest.raises((ValueError, Exception)):
        Timestamp(naive)


def test_value_equality() -> None:
    moment = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
    assert Timestamp(moment) == Timestamp(moment)


def test_now_is_close_to_real_now() -> None:
    before = datetime.now(tz=timezone.utc)
    ts = Timestamp.now()
    after = datetime.now(tz=timezone.utc)
    assert before <= ts.value <= after
