"""Unit tests for the ``SyncPolicy`` value object (DDD doc 06, §SyncPolicy).

Default policy is ``automated=True``, ``prune=True``, ``self_heal=True``,
``create_namespace=True`` — the project standard from ADR-0003 / ADR-0017.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
SyncPolicy = values.SyncPolicy

pytestmark = pytest.mark.unit


def test_default_is_project_standard() -> None:
    p = SyncPolicy()
    assert p.automated is True
    assert p.prune is True
    assert p.self_heal is True
    assert p.create_namespace is True


def test_overrides_supported() -> None:
    p = SyncPolicy(automated=False, prune=False, self_heal=False, create_namespace=False)
    assert not p.automated
    assert not p.prune
    assert not p.self_heal
    assert not p.create_namespace


def test_value_equality() -> None:
    assert SyncPolicy() == SyncPolicy()
    assert SyncPolicy(automated=False) != SyncPolicy(automated=True)


def test_immutable() -> None:
    p = SyncPolicy()
    with pytest.raises((AttributeError, Exception)):
        p.automated = False  # type: ignore[misc]
