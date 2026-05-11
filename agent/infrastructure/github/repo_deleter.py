"""Adapter implementing :class:`RepositoryDeleterPort` against PyGithub."""
from __future__ import annotations

from agent.application.cleanup import RepositoryDeleterPort
from agent.infrastructure.github.adapter import PyGithubAdapter


class PyGithubRepositoryDeleter(RepositoryDeleterPort):
    def __init__(self, github: PyGithubAdapter) -> None:
        self._github = github

    def delete(self, owner: str, name: str) -> None:
        self._github.delete_repository(owner, name)
