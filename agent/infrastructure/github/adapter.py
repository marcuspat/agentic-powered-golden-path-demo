"""GitHub ACL — wraps PyGithub.

Translates PyGithub exceptions into the domain exception hierarchy.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Optional

from agent.domain.errors import (
    ExternalSystemError,
    RateLimited,
    RepositoryAlreadyExists,
    RepositoryQuotaExceeded,
    Unauthorized,
)
from agent.domain.values import AppName, RepositoryUrl

logger = logging.getLogger(__name__)


class PyGithubAdapter:
    """Thin wrapper. Lazily imports PyGithub so unit tests don't need it."""

    def __init__(self, token: Optional[str] = None, *, owner: Optional[str] = None) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._owner = owner or os.environ.get("GITHUB_USERNAME")
        self._client = None
        self._user = None

    def _ensure(self):
        if self._client is not None:
            return self._client
        if not self._token:
            raise Unauthorized("GITHUB_TOKEN is not set")
        try:
            from github import Github  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ExternalSystemError("github", exc) from exc
        self._client = Github(self._token)
        try:
            self._user = self._client.get_user()
            if self._owner is None:
                self._owner = self._user.login
        except Exception as exc:
            raise self._translate(exc)
        return self._client

    @property
    def owner(self) -> str:
        if self._owner is None:
            self._ensure()
        if self._owner is None:
            raise Unauthorized("GitHub owner unknown; set GITHUB_USERNAME")
        return self._owner

    def create_repository(
        self,
        app_name: AppName,
        kind: str,
        description: str,
        *,
        private: bool = False,
        auto_init: bool = True,
    ) -> RepositoryUrl:
        if kind not in ("source", "gitops"):
            raise ValueError(f"kind must be 'source' or 'gitops', got {kind!r}")
        self._ensure()
        repo_name = f"{app_name.value}-{kind}"
        try:
            assert self._user is not None
            repo = self._user.create_repo(
                repo_name,
                description=description,
                private=private,
                auto_init=auto_init,
            )
            logger.info("github.repo_created name=%s", repo.full_name)
            return RepositoryUrl(repo.clone_url)
        except Exception as exc:
            translated = self._translate(exc)
            if isinstance(translated, RepositoryAlreadyExists):
                logger.warning(
                    "github.repo_already_exists name=%s — using canonical URL",
                    repo_name,
                )
                return RepositoryUrl.from_app(app_name, kind, self.owner)
            raise translated

    def delete_repository(self, owner: str, name: str) -> None:
        """Delete a GitHub repository. Destructive; no auto-rollback."""
        self._ensure()
        try:
            assert self._client is not None
            repo = self._client.get_repo(f"{owner}/{name}")
            repo.delete()
            logger.info("github.repo_deleted owner=%s name=%s", owner, name)
        except Exception as exc:
            translated = self._translate(exc)
            cls = type(exc).__name__
            if cls == "UnknownObjectException":
                logger.info("github.repo_not_found owner=%s name=%s (treated as success)", owner, name)
                return
            raise translated

    @staticmethod
    def _translate(exc: BaseException) -> BaseException:
        # Inspect by class name so we don't import github at module level.
        cls = type(exc).__name__
        msg = str(exc)
        if cls == "BadCredentialsException":
            return Unauthorized(f"GitHub auth failure: {msg}")
        if cls == "RateLimitExceededException":
            return RateLimited(f"GitHub rate limited: {msg}", retry_after=timedelta(minutes=5))
        if cls == "GithubException":
            # Heuristics on the GitHub message body.
            lower = msg.lower()
            if "name already exists" in lower or "already exists on this account" in lower:
                return RepositoryAlreadyExists(msg)
            if "quota" in lower or "over your repository limit" in lower:
                return RepositoryQuotaExceeded(msg)
            if "bad credentials" in lower or "401" in lower:
                return Unauthorized(msg)
            return ExternalSystemError("github", exc)
        return ExternalSystemError("github", exc)
