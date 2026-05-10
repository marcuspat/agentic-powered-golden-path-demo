"""End-to-end onboarding test against a live cluster + GitHub.

Skipped by default. Set ``RUN_E2E=1`` to run, plus the credentials documented
in ADR-0014:

- ``GITHUB_TOKEN``
- ``GITHUB_USERNAME``
- ``OPENROUTER_API_KEY``

This test must NEVER be run from a fork PR — see ADR-0015 §Compliance.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

if os.getenv("RUN_E2E") != "1":
    pytest.skip("Set RUN_E2E=1 to run the e2e tier", allow_module_level=True)

pytestmark = [pytest.mark.e2e]


_REQUIRED_ENV = ("GITHUB_TOKEN", "GITHUB_USERNAME", "OPENROUTER_API_KEY")


@pytest.fixture(scope="module")
def _e2e_env_present() -> None:
    missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
    if missing:
        pytest.skip(f"E2E env vars missing: {', '.join(missing)}")


@pytest.fixture(scope="module")
def _kubectl_available() -> None:
    if shutil.which("kubectl") is None:
        pytest.skip("kubectl not on PATH")


def test_e2e_flow_smoke(_e2e_env_present: None, _kubectl_available: None) -> None:
    """The smoke shape; full assertions live with the platform team's harness.

    This test deliberately stays at the shape level so it is safe to extend:
    real assertions about cluster state belong in the nightly suite.
    """
    # Cluster must be reachable
    proc = subprocess.run(
        ["kubectl", "cluster-info"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"kubectl cluster-info failed: {proc.stderr}"

    # The agent must be invokable; the orchestrator slice owns the actual
    # implementation. We check only that the entry point exists.
    repo_root = Path(__file__).resolve().parent.parent.parent
    agent_pkg = repo_root / "agent"
    assert agent_pkg.exists(), "agent/ package not present; orchestrator hasn't landed"
