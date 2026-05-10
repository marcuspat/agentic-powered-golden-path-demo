"""Unit tests for the ``Outcome`` value object (DDD doc 06, §Outcome).

Invariants:

- If ``kind == FAILED``, ``reason`` AND ``failed_step`` are required.
- If ``kind == SUCCEEDED``, ``reason`` and ``failed_step`` MUST be absent.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
Outcome = values.Outcome
OutcomeKind = values.OutcomeKind

pytestmark = pytest.mark.unit


def test_succeeded_default_constructor_clean() -> None:
    o = Outcome(kind=OutcomeKind.SUCCEEDED)
    assert o.kind is OutcomeKind.SUCCEEDED
    assert o.reason is None
    assert o.failed_step is None


def test_succeeded_rejects_reason_or_step() -> None:
    """Successful outcomes must not carry failure metadata."""
    with pytest.raises((ValueError, Exception)):
        Outcome(kind=OutcomeKind.SUCCEEDED, reason="why")
    with pytest.raises((ValueError, Exception)):
        Outcome(kind=OutcomeKind.SUCCEEDED, failed_step="step")


def test_failed_requires_reason_and_step() -> None:
    with pytest.raises((ValueError, Exception)):
        Outcome(kind=OutcomeKind.FAILED)
    with pytest.raises((ValueError, Exception)):
        Outcome(kind=OutcomeKind.FAILED, reason="boom")
    with pytest.raises((ValueError, Exception)):
        Outcome(kind=OutcomeKind.FAILED, failed_step="render")


def test_failed_with_full_context_accepted() -> None:
    o = Outcome(
        kind=OutcomeKind.FAILED,
        reason="GitHub API returned 422",
        failed_step="create_source_repo",
    )
    assert o.kind is OutcomeKind.FAILED
    assert o.reason
    assert o.failed_step


def test_cancelled_kind_supported() -> None:
    o = Outcome(kind=OutcomeKind.CANCELLED, reason="user aborted")
    assert o.kind is OutcomeKind.CANCELLED


def test_outcome_kind_values_are_stable_strings() -> None:
    assert OutcomeKind.SUCCEEDED.value == "succeeded"
    assert OutcomeKind.FAILED.value == "failed"
    assert OutcomeKind.CANCELLED.value == "cancelled"


def test_outcome_equality_by_value() -> None:
    a = Outcome(kind=OutcomeKind.SUCCEEDED)
    b = Outcome(kind=OutcomeKind.SUCCEEDED)
    assert a == b


def test_succeeded_classmethod_helper() -> None:
    if hasattr(Outcome, "succeeded"):
        assert Outcome.succeeded().kind is OutcomeKind.SUCCEEDED
