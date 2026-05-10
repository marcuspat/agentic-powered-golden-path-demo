"""GitHub-backed SourceRepository repository."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import List

from agent.domain.aggregates.source_repository import SourceRepository
from agent.domain.ports import GitWorkingCopyPort, SourceRepositoryPort
from agent.domain.values import (
    AppDescription,
    AppName,
    BranchName,
    CommitMessage,
    GitSha,
    RenderedFile,
)
from agent.infrastructure.github.adapter import PyGithubAdapter

logger = logging.getLogger(__name__)


class GitHubSourceRepoRepository(SourceRepositoryPort):
    def __init__(self, github: PyGithubAdapter, git: GitWorkingCopyPort) -> None:
        self._github = github
        self._git = git

    def create(self, app_name: AppName, description: AppDescription) -> SourceRepository:
        url = self._github.create_repository(
            app_name=app_name,
            kind="source",
            description=description.text,
        )
        return SourceRepository.newly_created(app_name=app_name, url=url)

    def populate(
        self,
        repo: SourceRepository,
        files: List[RenderedFile],
        message: CommitMessage,
        branch: BranchName = BranchName(),
    ) -> GitSha:
        with tempfile.TemporaryDirectory(prefix="gpagent-src-") as tmp:
            wc = Path(tmp) / repo.url.repo_name
            try:
                self._git.clone(repo.url, wc)
                self._git.write_files(wc, files)
                sha = self._git.commit_all(wc, message)
                self._git.push(wc, branch)
            except Exception:
                repo.mark_failed()
                raise
        repo.mark_populated(message, sha)
        return sha
