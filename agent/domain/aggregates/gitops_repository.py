"""GitOpsRepository aggregate — BC-4 GitOps Configuration."""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.domain.values import (
    AppName,
    CommitMessage,
    GitSha,
    ManifestKind,
    Namespace,
    RepositoryUrl,
    RepoStatus,
    Timestamp,
)


@dataclass
class GitOpsRepository:
    app_name: AppName
    url: RepositoryUrl
    created_at: Timestamp
    target_namespace: Namespace
    status: RepoStatus = RepoStatus.EMPTY
    manifests: list[ManifestKind] = field(default_factory=list)
    initial_commit: CommitMessage | None = None
    initial_sha: GitSha | None = None

    @classmethod
    def newly_created(
        cls,
        app_name: AppName,
        url: RepositoryUrl,
        namespace: Namespace,
    ) -> GitOpsRepository:
        return cls(
            app_name=app_name,
            url=url,
            created_at=Timestamp.now(),
            target_namespace=namespace,
        )

    def mark_populated(
        self,
        message: CommitMessage,
        sha: GitSha,
        manifests: list[ManifestKind],
    ) -> None:
        if self.status is RepoStatus.POPULATED:
            raise ValueError(f"GitOpsRepository {self.app_name} already populated")
        if self.status is RepoStatus.FAILED:
            raise ValueError(
                f"Cannot populate failed GitOpsRepository {self.app_name}"
            )
        self.status = RepoStatus.POPULATED
        self.initial_commit = message
        self.initial_sha = sha
        self.manifests = list(manifests)

    def mark_failed(self) -> None:
        self.status = RepoStatus.FAILED
