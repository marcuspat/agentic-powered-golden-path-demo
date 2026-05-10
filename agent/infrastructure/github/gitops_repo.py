"""GitHub-backed GitOpsRepository repository."""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import List

from agent.domain.aggregates.gitops_repository import GitOpsRepository
from agent.domain.ports import GitOpsRepositoryPort, GitWorkingCopyPort
from agent.domain.values import (
    AppDescription,
    AppName,
    BranchName,
    CommitMessage,
    GitSha,
    ManifestKind,
    Namespace,
    RenderedFile,
)
from agent.infrastructure.github.adapter import PyGithubAdapter

logger = logging.getLogger(__name__)


class GitHubGitOpsRepoRepository(GitOpsRepositoryPort):
    def __init__(self, github: PyGithubAdapter, git: GitWorkingCopyPort) -> None:
        self._github = github
        self._git = git

    def create(self, app_name: AppName, description: AppDescription) -> GitOpsRepository:
        url = self._github.create_repository(
            app_name=app_name,
            kind="gitops",
            description=description.text,
        )
        return GitOpsRepository.newly_created(
            app_name=app_name,
            url=url,
            namespace=Namespace.from_app(app_name),
        )

    def populate(
        self,
        repo: GitOpsRepository,
        files: List[RenderedFile],
        message: CommitMessage,
        branch: BranchName = BranchName(),
    ) -> GitSha:
        with tempfile.TemporaryDirectory(prefix="gpagent-gitops-") as tmp:
            wc = Path(tmp) / repo.url.repo_name
            try:
                self._git.clone(repo.url, wc)
                self._git.write_files(wc, files)
                sha = self._git.commit_all(wc, message)
                self._git.push(wc, branch)
            except Exception:
                repo.mark_failed()
                raise
        repo.mark_populated(message, sha, _scan_manifest_kinds(files))
        return sha


_KIND_RE = re.compile(rb"^kind:\s*([A-Za-z]+)\s*$", re.MULTILINE)


def _scan_manifest_kinds(files: List[RenderedFile]) -> List[ManifestKind]:
    kinds: list[ManifestKind] = []
    seen: set[str] = set()
    for f in files:
        if not (f.relative_path.endswith(".yaml") or f.relative_path.endswith(".yml")):
            continue
        for m in _KIND_RE.finditer(f.content):
            name = m.group(1).decode("utf-8")
            if name in seen:
                continue
            seen.add(name)
            try:
                kinds.append(ManifestKind(name))
            except ValueError:
                continue  # unknown kinds are silently ignored
    return kinds
