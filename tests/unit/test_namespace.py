"""Unit tests for the ``Namespace`` value object (DDD doc 06, §Namespace).

``Namespace`` is a DNS label, like ``AppName``, and is *often* equal to it
(ADR-0017). The two are kept as distinct types so the model is explicit
about *what role* a string plays.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
Namespace = values.Namespace

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "ns",
    [
        "default",
        "inventory-api",
        "kube-system",
        "argocd",
        "a",
        "a" * 63,
    ],
)
def test_valid_namespaces_accepted(ns: str) -> None:
    assert Namespace(ns).value == ns


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "Has-Upper",
        "_underscore",
        "with space",
        "-dash",
        "dash-",
        "a" * 64,
    ],
)
def test_invalid_namespaces_rejected(bad: str) -> None:
    with pytest.raises((ValueError, Exception)):
        Namespace(bad)


def test_namespace_distinct_type_from_app_name() -> None:
    """The two are not interchangeable; types catch role confusion at boundaries."""
    AppName = values.AppName
    assert isinstance(Namespace("a"), Namespace)
    assert not isinstance(Namespace("a"), AppName)
