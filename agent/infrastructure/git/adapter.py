"""git CLI ACL — list-form subprocess invocations only.

See ``docs/ddd/11-anti-corruption-layers.md`` for the translation rules.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from agent.domain.errors import (
    ExternalSystemError,
    GitOutOfDate,
    Unauthorized,
)
from agent.domain.ports import GitWorkingCopyPort
from agent.domain.values import (
    BranchName,
    CommitMessage,
    GitSha,
    RenderedFile,
    RepositoryUrl,
)

logger = logging.getLogger(__name__)


class GitCliAdapter(GitWorkingCopyPort):
    """Wraps the local ``git`` CLI."""

    def __init__(self, *, default_user_name: str = "Golden Path Agent",
                 default_user_email: str = "agent@golden-path.local") -> None:
        self._user_name = default_user_name
        self._user_email = default_user_email

    def clone(self, url: RepositoryUrl, into: Path) -> None:
        dest = Path(into)
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._run(["git", "clone", url.value, str(dest)])
        # Configure committer identity so commits work without global config.
        self._run(["git", "-C", str(dest), "config", "user.name", self._user_name])
        self._run(["git", "-C", str(dest), "config", "user.email", self._user_email])

    def write_files(self, working_copy_dir: Path, files: list[RenderedFile]) -> None:
        root = Path(working_copy_dir)
        for f in files:
            target = root / f.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(f.content)

    def commit_all(self, working_copy_dir: Path, message: CommitMessage) -> GitSha:
        root = Path(working_copy_dir)
        self._run(["git", "-C", str(root), "add", "-A"])
        # Detect "nothing to commit" by checking porcelain status.
        status = self._run(["git", "-C", str(root), "status", "--porcelain"])
        if not status.strip():
            sha = self._run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
            return GitSha(sha)
        self._run(["git", "-C", str(root), "commit", "-m", message.value])
        sha = self._run(["git", "-C", str(root), "rev-parse", "HEAD"]).strip()
        return GitSha(sha)

    def push(self, working_copy_dir: Path, branch: BranchName) -> None:
        root = Path(working_copy_dir)
        # If repo was just initialised we may need to set the upstream.
        try:
            self._run(["git", "-C", str(root), "push", "origin", branch.value])
        except (Unauthorized, GitOutOfDate):
            raise
        except ExternalSystemError as exc:
            # Fall back to setting upstream explicitly if origin not set.
            stderr = str(exc)
            if "set-upstream" in stderr or "no upstream" in stderr:
                self._run(["git", "-C", str(root), "push", "-u", "origin", branch.value])
            else:
                raise

    def revert(
        self,
        url: RepositoryUrl,
        target_sha: GitSha | None,
        message: CommitMessage,
    ) -> tuple[GitSha, GitSha]:
        with tempfile.TemporaryDirectory(prefix="gpagent-revert-") as tmp:
            self.clone(url, Path(tmp) / url.repo_name)
            wc = Path(tmp) / url.repo_name
            sha = target_sha.value if target_sha else self._run(
                ["git", "-C", str(wc), "rev-parse", "HEAD"]
            ).strip()
            self._run([
                "git", "-C", str(wc), "revert", "--no-edit", sha,
            ])
            new_head = self._run(["git", "-C", str(wc), "rev-parse", "HEAD"]).strip()
            self.push(wc, BranchName())
            return GitSha(sha), GitSha(new_head)

    # ----- internals ----- #

    def _run(self, args: list[str]) -> str:
        logger.debug("git.exec %s", args)
        proc = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        if proc.returncode == 0:
            return proc.stdout
        stderr = proc.stderr or ""
        lower = stderr.lower()
        if "authentication failed" in lower or "could not read username" in lower:
            raise Unauthorized(f"git auth failure: {stderr.strip()}")
        if "non-fast-forward" in lower or "fetch first" in lower:
            raise GitOutOfDate(f"git out of date: {stderr.strip()}")
        raise ExternalSystemError("git", RuntimeError(stderr.strip() or proc.stdout.strip()))
