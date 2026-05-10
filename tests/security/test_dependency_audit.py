"""Run ``pip-audit`` against the project's pinned dependencies.

Skips cleanly when ``pip-audit`` is not installed so the test does not
break local checkouts; CI is expected to ensure ``pip-audit`` is present
(see ``requirements-dev.txt``).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.security


@pytest.fixture
def pip_audit_available() -> str:
    binary = shutil.which("pip-audit")
    if binary is None:
        pytest.skip("pip-audit not installed; install via requirements-dev.txt")
    return binary


def _requirements_file(repo_root: Path) -> Path:
    req = repo_root / "requirements.txt"
    if not req.exists():
        pytest.skip("requirements.txt not found")
    return req


def test_pip_audit_finds_no_known_cves(
    pip_audit_available: str, repo_root: Path
) -> None:
    req = _requirements_file(repo_root)

    proc = subprocess.run(
        [
            pip_audit_available,
            "--requirement",
            str(req),
            "--format",
            "json",
            "--strict",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    # pip-audit exits non-zero on findings; print the report on failure.
    if proc.returncode != 0:
        try:
            findings = json.loads(proc.stdout or "[]")
        except json.JSONDecodeError:
            findings = proc.stdout or proc.stderr
        pytest.fail(f"pip-audit reported vulnerabilities:\n{findings}")
