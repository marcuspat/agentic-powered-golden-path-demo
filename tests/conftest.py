"""Shared pytest fixtures and configuration for the Golden Path test suite.

This file is the single source of truth for cross-tier fixtures. Tier-local
fixtures, when needed, may live in ``tests/<tier>/conftest.py``.

Conventions:

- Tests must never read or write the developer's real environment. The
  ``_isolate_env`` autouse fixture strips known secrets per ADR-0014 and
  per the security tier's "no env leakage" rule.
- Tests must never write outside ``tmp_path``. Filesystem fixtures here
  return ``pathlib.Path`` objects rooted at ``tmp_path``.
- The ``REPO_ROOT`` constant resolves to the repository root so tests can
  reference the live ``cnoe-stacks/``, ``templates/``, and (future)
  ``agent/`` trees without hard-coding container paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
"""Absolute path to the repository root."""

# Make the repo root importable so ``import agent.domain.values`` works once
# the orchestrator's slice lands the package. This is harmless if the package
# is absent — the unit tests use ``pytest.importorskip`` to defer.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------

_SECRET_ENV_VARS = (
    "GITHUB_TOKEN",
    "GITHUB_USERNAME",
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENAI_API_KEY",
    "KUBECONFIG",
    "STACK_DIR",
    "LOG_LEVEL",
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip known agent env vars so tests cannot accidentally rely on them.

    Per ADR-0014 the agent's behaviour is fully driven by environment
    variables. To keep tests deterministic we wipe those variables for every
    test and let the test re-set what it needs via ``monkeypatch.setenv``.

    E2E tests opt out by setting ``RUN_E2E=1`` *outside* the test process;
    this fixture preserves ``RUN_E2E`` so the e2e tier can detect it.
    """
    for name in _SECRET_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root() -> Path:
    """Return the absolute path to the repo root."""
    return REPO_ROOT


@pytest.fixture
def stack_dir(repo_root: Path) -> Path:
    """Return the live ``cnoe-stacks/`` directory."""
    return repo_root / "cnoe-stacks"


@pytest.fixture
def templates_dir(repo_root: Path) -> Path:
    """Return the live ``templates/`` directory."""
    return repo_root / "templates"


@pytest.fixture
def agent_dir(repo_root: Path) -> Path:
    """Return the (future) ``agent/`` package directory.

    Tests that walk this tree should ``pytest.skip`` when it does not yet
    exist; the orchestrator's parallel slice lands it.
    """
    return repo_root / "agent"


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Iterator[Path]:
    """Yield a fresh temporary workspace; clean-up is handled by ``tmp_path``."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    yield workspace


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_app_name() -> str:
    """A canonical, well-formed app name used across tests."""
    return "inventory-api"


@pytest.fixture
def sample_correlation_uuid() -> str:
    """A stable, deterministic UUIDv4 string for tests that need one."""
    return "11111111-2222-4333-8444-555555555555"
