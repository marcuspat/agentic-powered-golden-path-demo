"""Unit tests for the ``ContainerImage`` value object (DDD doc 06, §ContainerImage).

Rules:

- ``str()`` produces ``"<registry>/<repository>:<tag>"``.
- ``tag`` of ``"latest"`` is permitted but flagged in production manifests.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
ContainerImage = values.ContainerImage
ImageTag = values.ImageTag

pytestmark = pytest.mark.unit


def test_str_assembles_registry_repository_tag() -> None:
    image = ContainerImage(
        registry="ghcr.io",
        repository="acme/inventory-api",
        tag=ImageTag("v1.2.3"),
    )
    assert str(image) == "ghcr.io/acme/inventory-api:v1.2.3"


def test_value_equality() -> None:
    a = ContainerImage("ghcr.io", "acme/svc", ImageTag("v1"))
    b = ContainerImage("ghcr.io", "acme/svc", ImageTag("v1"))
    assert a == b


def test_different_tag_distinct() -> None:
    a = ContainerImage("ghcr.io", "acme/svc", ImageTag("v1"))
    b = ContainerImage("ghcr.io", "acme/svc", ImageTag("v2"))
    assert a != b


@pytest.mark.parametrize("tag", ["v1.0.0", "v2.3.4-rc1", "1.0", "build-123"])
def test_tag_accepts_common_formats(tag: str) -> None:
    assert ImageTag(tag).value == tag


def test_tag_rejects_empty() -> None:
    with pytest.raises((ValueError, Exception)):
        ImageTag("")
