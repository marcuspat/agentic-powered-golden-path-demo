"""SourceRepository aggregate — BC-3 Source Provisioning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agent.domain.values import (
    AppName,
    CommitMessage,
    GitSha,
    RepoStatus,
    RepositoryUrl,
    Timestamp,
)


@dataclass
class SourceRepository:
    app_name: AppName
    url: RepositoryUrl
    created_at: Timestamp
    status: RepoStatus = RepoStatus.EMPTY
    initial_commit: Optional[CommitMessage] = None
    initial_sha: Optional[GitSha] = None

    @classmethod
    def newly_created(cls, app_name: AppName, url: RepositoryUrl) -> "SourceRepository":
        return cls(app_name=app_name, url=url, created_at=Timestamp.now())

    def mark_populated(self, message: CommitMessage, sha: GitSha) -> None:
        if self.status is RepoStatus.POPULATED:
            raise ValueError(f"SourceRepository {self.app_name} already populated")
        if self.status is RepoStatus.FAILED:
            raise ValueError(
                f"Cannot populate failed SourceRepository {self.app_name}"
            )
        self.status = RepoStatus.POPULATED
        self.initial_commit = message
        self.initial_sha = sha

    def mark_failed(self) -> None:
        self.status = RepoStatus.FAILED
