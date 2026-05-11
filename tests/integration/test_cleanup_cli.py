"""Integration test for the ``agent cleanup`` CLI subcommand.

Replaces :func:`agent.composition.build_cleanup_service` with a stub builder
so the CLI is exercised end-to-end without touching kubectl or GitHub.
"""
from __future__ import annotations

import os
from typing import List

import pytest

cli_mod = pytest.importorskip("agent.cli", reason="agent.cli not yet landed")
cleanup_mod = pytest.importorskip(
    "agent.application.cleanup", reason="agent.application.cleanup not yet landed"
)
composition_mod = pytest.importorskip(
    "agent.composition", reason="agent.composition not yet landed"
)

pytestmark = pytest.mark.integration


class _FakeArgo:
    def __init__(self) -> None:
        self.removed: List[str] = []

    def register(self, _app):  # pragma: no cover
        pass

    def get(self, _name):  # pragma: no cover
        return None

    def remove(self, name) -> None:
        self.removed.append(name.value)


class _FakeKubectl:
    def __init__(self) -> None:
        self.deleted: List = []

    def get_json(self, *_args, **_kwargs):  # pragma: no cover
        raise NotImplementedError

    def delete(self, resource, name, *, namespace=None, ignore_not_found=True):
        self.deleted.append((resource, name, namespace.value if namespace else None))


class _FakeRepoDeleter:
    def __init__(self) -> None:
        self.deleted: List = []

    def delete(self, owner: str, name: str) -> None:
        self.deleted.append((owner, name))


@pytest.fixture
def fake_cleanup_service(monkeypatch: pytest.MonkeyPatch):
    argo = _FakeArgo()
    kubectl = _FakeKubectl()
    repo_deleter = _FakeRepoDeleter()
    svc = cleanup_mod.CleanupApplicationService(
        argo_repo=argo,
        kubectl_read=kubectl,
        repo_deleter=repo_deleter,
        github_owner="acme",
    )

    def _build():
        return svc

    monkeypatch.setattr(composition_mod, "build_cleanup_service", _build)
    monkeypatch.setattr(cli_mod, "build_cleanup_service", _build)
    return svc, argo, kubectl, repo_deleter


def test_cleanup_cli_invokes_service_and_exits_zero(
    fake_cleanup_service, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("GITHUB_USERNAME", "acme")
    code = cli_mod.main(["cleanup", "inventory-api"])
    assert code == 0
    svc, argo, kubectl, repo_deleter = fake_cleanup_service
    assert argo.removed == ["inventory-api"]
    assert kubectl.deleted == [("namespace", "inventory-api", None)]
    assert repo_deleter.deleted == []  # default: --repos not set
    captured = capsys.readouterr()
    assert "Cleanup completed" in captured.out


def test_cleanup_cli_with_repos_flag(
    fake_cleanup_service, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_USERNAME", "acme")
    code = cli_mod.main(["cleanup", "billing", "--repos"])
    assert code == 0
    _, _, _, repo_deleter = fake_cleanup_service
    assert repo_deleter.deleted == [
        ("acme", "billing-source"),
        ("acme", "billing-gitops"),
    ]


def test_cleanup_cli_rejects_invalid_app_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_USERNAME", "acme")
    code = cli_mod.main(["cleanup", "Invalid Name With Spaces"])
    assert code == 2


def test_cleanup_cli_keep_namespace(
    fake_cleanup_service, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_USERNAME", "acme")
    code = cli_mod.main(["cleanup", "billing", "--keep-namespace"])
    assert code == 0
    _, _, kubectl, _ = fake_cleanup_service
    assert kubectl.deleted == []
