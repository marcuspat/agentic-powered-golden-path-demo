"""Unit tests for the ``AppName`` value object (DDD doc 06, §AppName).

These tests pin the rules:

- Lowercase ASCII only.
- ``a-z``, ``0-9``, ``-``; must start and end with ``[a-z0-9]``.
- Length 1-63 (RFC 1123 DNS label).
- ``AppName.from_raw`` is the only sanitiser; both the LLM path and the
  regex path in ``IntentExtractionService`` must route through it.

``AppName.from_raw`` normalises whitespace, ``_`` and ``.`` to ``-`` before
stripping any other non-alphanumeric character.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
AppName = values.AppName

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Direct construction — happy path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "a",
        "x1",
        "inventory-api",
        "payments-svc",
        "order-service-v2",
        "abc123",
        "a" * 63,
    ],
)
def test_valid_app_names_accepted(name: str) -> None:
    assert AppName(name).value == name
    assert str(AppName(name)) == name


# ---------------------------------------------------------------------------
# Direct construction — rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "-leading",
        "trailing-",
        "Has-Upper",
        "spaces here",
        "under_score",
        "dot.name",
        "a" * 64,
        "1bad/char",
    ],
)
def test_invalid_app_names_rejected(bad: str) -> None:
    with pytest.raises(ValueError):
        AppName(bad)


# ---------------------------------------------------------------------------
# Normalisation via ``from_raw``
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Whitespace and ``_``/``.`` collapse to a single ``-``.
        ("Inventory API", "inventory-api"),
        ("  Trim Me  ", "trim-me"),
        ("payments--svc", "payments-svc"),
        ("--LEADING--", "leading"),
        ("Order Service v2!", "order-service-v2"),
        ("snake_case_name", "snake-case-name"),
        ("dot.notation.name", "dot-notation-name"),
        ("a" * 70, "a" * 63),
    ],
)
def test_from_raw_normalises(raw: str, expected: str) -> None:
    assert AppName.from_raw(raw).value == expected


def test_from_raw_rejects_empty_after_normalisation() -> None:
    with pytest.raises(ValueError):
        AppName.from_raw("!!!")


def test_from_raw_rejects_none() -> None:
    with pytest.raises(ValueError):
        AppName.from_raw(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Equality / hashability (frozen dataclass guarantees)
# ---------------------------------------------------------------------------


def test_value_equality() -> None:
    assert AppName("inventory-api") == AppName("inventory-api")
    assert AppName.from_raw("Inventory-API") == AppName("inventory-api")


def test_hashable_for_set_and_dict() -> None:
    s = {AppName("a"), AppName("a"), AppName("b")}
    assert len(s) == 2


def test_immutable() -> None:
    name = AppName("svc")
    with pytest.raises((AttributeError, Exception)):
        name.value = "other"  # type: ignore[misc]
