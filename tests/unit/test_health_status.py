"""Unit tests for the ``HealthStatus`` and ``SyncStatus`` enums (DDD doc 06).

These mirror ArgoCD's vocabulary. They are kept inside the ACL so that, if
ArgoCD adds a new value, only the ACL's mapping needs to change.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
HealthStatus = values.HealthStatus
SyncStatus = values.SyncStatus

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "name,expected",
    [
        ("HEALTHY", "Healthy"),
        ("PROGRESSING", "Progressing"),
        ("DEGRADED", "Degraded"),
        ("SUSPENDED", "Suspended"),
        ("MISSING", "Missing"),
        ("UNKNOWN", "Unknown"),
    ],
)
def test_health_status_strings(name: str, expected: str) -> None:
    member = HealthStatus[name]
    assert member.value == expected
    assert str(member.value) == expected


@pytest.mark.parametrize(
    "name,expected",
    [
        ("SYNCED", "Synced"),
        ("OUT_OF_SYNC", "OutOfSync"),
        ("UNKNOWN", "Unknown"),
    ],
)
def test_sync_status_strings(name: str, expected: str) -> None:
    member = SyncStatus[name]
    assert member.value == expected


def test_health_status_construction_from_value() -> None:
    assert HealthStatus("Healthy") is HealthStatus.HEALTHY
    assert HealthStatus("Degraded") is HealthStatus.DEGRADED


def test_unknown_health_value_rejected() -> None:
    with pytest.raises(ValueError):
        HealthStatus("NotARealStatus")


def test_unknown_sync_value_rejected() -> None:
    with pytest.raises(ValueError):
        SyncStatus("NotARealStatus")
