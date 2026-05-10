"""Unit tests for the ``RepositoryUrl`` value object (DDD doc 06, §RepositoryUrl).

Rules:

- Must be HTTPS.
- Must end with ``.git``.
- Path segments: exactly two (owner / repo).
- ``RepositoryUrl.from_app(app_name, kind, owner)`` builds the canonical URL,
  with ``kind`` restricted to ``"source"`` or ``"gitops"``.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
RepositoryUrl = values.RepositoryUrl
AppName = values.AppName

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/inventory-api.git",
        "https://github.com/acme/inventory-api-gitops.git",
        "https://github.com/me/repo.git",
    ],
)
def test_valid_https_urls_accepted(url: str) -> None:
    assert RepositoryUrl(url).value == url


@pytest.mark.parametrize(
    "bad",
    [
        "http://github.com/acme/repo.git",         # not https
        "github.com/acme/repo.git",                 # no scheme
        "https://github.com/acme/repo",             # no .git
        "https://github.com/acme/repo/",            # trailing slash, no .git
        "https://github.com/acme.git",              # missing repo segment
        "https://github.com/acme/repo/extra.git",   # too many segments
        "",
    ],
)
def test_invalid_urls_rejected(bad: str) -> None:
    with pytest.raises((ValueError, Exception)):
        RepositoryUrl(bad)


def test_from_app_builds_source_url() -> None:
    url = RepositoryUrl.from_app(AppName("inventory-api"), "source", "acme")
    assert url.value == "https://github.com/acme/inventory-api-source.git"


def test_from_app_builds_gitops_url() -> None:
    url = RepositoryUrl.from_app(AppName("inventory-api"), "gitops", "acme")
    assert url.value == "https://github.com/acme/inventory-api-gitops.git"


def test_from_app_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        RepositoryUrl.from_app(AppName("inventory-api"), "weird", "acme")


def test_repo_name_helper() -> None:
    url = RepositoryUrl("https://github.com/acme/inventory-api-gitops.git")
    assert url.repo_name == "inventory-api-gitops"


def test_owner_helper() -> None:
    url = RepositoryUrl("https://github.com/acme/inventory-api-gitops.git")
    assert url.owner == "acme"


def test_value_equality() -> None:
    assert RepositoryUrl("https://github.com/a/b.git") == RepositoryUrl(
        "https://github.com/a/b.git"
    )
