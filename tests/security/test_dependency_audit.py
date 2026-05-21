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


# Triaged advisories with no applicable fix. Each entry is reviewed and
# justified; revisit when a patched release lands.
#
# PYSEC-2024-278 (CVE-2024-2057) — SSRF in langchain_community's
#   TFIDFRetriever.load_local. The vuln DB records no fixed version for the
#   0.3.x line, and this project never imports TFIDFRetriever.
# PYSEC-2025-183 (CVE-2025-45768) — "weak encryption" in PyJWT, disputed by
#   the maintainers (key length is chosen by the calling application). Pulled
#   in transitively by PyGithub; no fixed release exists.
IGNORED_VULN_IDS = (
    "PYSEC-2024-278",
    "PYSEC-2025-183",
)


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

    cmd = [
        pip_audit_available,
        "--requirement",
        str(req),
        "--format",
        "json",
        "--strict",
    ]
    for vuln_id in IGNORED_VULN_IDS:
        cmd.extend(["--ignore-vuln", vuln_id])

    proc = subprocess.run(
        cmd,
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
