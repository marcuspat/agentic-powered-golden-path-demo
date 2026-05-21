"""Shared helpers for the security tier.

Centralises the secret-pattern catalogue, file walker, and the
``scan(roots)`` entry point so that tests, perf benches, and any future
pre-commit hook all use exactly the same rules.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Pattern catalogue
# ---------------------------------------------------------------------------

# Each pattern targets a concrete shape of leaked secret. New patterns must
# include a short comment with an example of what they catch.
PATTERNS: Mapping[str, re.Pattern[str]] = {
    # password = "verysecret123"
    "password_literal": re.compile(r"password\s*[:=]\s*['\"][A-Za-z0-9!@#$%^&*()_+\-=]{8,}"),
    # Authorization: Bearer eyJhbGciOi...
    "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    # GitHub Personal Access Token (classic + fine-grained).
    "github_classic_pat": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    "github_fine_pat": re.compile(r"github_pat_[A-Za-z0-9_]{60,}"),
    # OpenAI / OpenRouter API keys.
    "openai_or_openrouter_key": re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    "openrouter_v1_key": re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    # AWS access keys.
    "aws_access_key_id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "aws_secret_access_key_assignment": re.compile(
        r"aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{30,}",
        re.IGNORECASE,
    ),
    # GCP service-account private key marker.
    "rsa_private_key": re.compile(r"-----BEGIN\s+RSA\s+PRIVATE\s+KEY-----"),
    "openssh_private_key": re.compile(r"-----BEGIN\s+OPENSSH\s+PRIVATE\s+KEY-----"),
    "pgp_private_key": re.compile(r"-----BEGIN\s+PGP\s+PRIVATE\s+KEY\s+BLOCK-----"),
    # Slack tokens.
    "slack_token": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    # JWT (header.payload.signature, all base64url).
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    # Generic "secret =" / "token =" with a long value.
    "generic_secret_assignment": re.compile(
        r"(?i)\b(secret|token|api[_\-]?key|passwd)\s*[:=]\s*['\"][A-Za-z0-9!@#$%^&*()_+\-=]{20,}"
    ),
    # Kubernetes ``Secret`` resources with concrete ``data:`` (vs. encrypted forms).
    # Catches both stringData and data. ExternalSecret/SealedSecret CRs do not
    # use ``kind: Secret`` so they are inherently excluded.
    "k8s_secret_data": re.compile(
        r"^kind:\s*Secret\s*$", re.MULTILINE
    ),
}

# Marker patterns. When present in a file, a known false-positive token is
# allowed. Use ``# noqa: secret-scan`` on the same line for a per-line skip.
LINE_ALLOW_MARKER = re.compile(r"#\s*noqa[: ]*\s*secret-scan", re.IGNORECASE)

# Words on the line that indicate the token is documentation, not a real leak.
DOC_HINTS = (
    "example",
    "placeholder",
    "sample",
    "your_",
    "<your-",
    "your-token",
    "redacted",
    "xxxxxxxx",
    "${",                      # shell var
    "{{",                      # jinja2 var
    "<<",                      # heredoc
)


# ---------------------------------------------------------------------------
# Walk configuration
# ---------------------------------------------------------------------------

EXCLUDE_FILE_NAMES = frozenset({
    ".env.example",
    "secret-scan.md",
})

# Extensions that are never source.
EXCLUDE_SUFFIXES = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
    ".pdf",
    ".tar", ".gz", ".zip", ".whl", ".jar",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".bin",
    ".lock",  # package-lock.json is huge; we whitelist if needed
})

EXCLUDE_DIR_NAMES = frozenset({
    ".git",
    "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache",
    "node_modules",
    ".venv", "venv", ".tox",
    "dist", "build",
    "idpbuilder-source",            # vendored upstream
    "ai-platform-engineering",      # vendored upstream
})

# Files whose presence in the catalogue path is *expected* to mention a
# secret keyword (in documentation, not as a leak). They are *not* skipped
# entirely — the line-level DOC_HINTS filter still applies — but a noisy
# false-positive in one of these gets its own allowlist entry below.
PATHS_WITH_DOCUMENTATION = (
    "docs/adr/0014-environment-variable-configuration.md",
    "docs/adr/0018-credential-management-approach.md",
    "docs/adr/0020-observability-strategy.md",
    "docs/ddd/06-value-objects.md",
    "docs/ddd/11-anti-corruption-layers.md",
    "README.md",
    "cnoe-stacks/nodejs-gitops-template/README.md",
    "cnoe-stacks/nodejs-gitops-template/externalsecret.yaml",
    "cnoe-stacks/nodejs-template/.tekton/README.md",
    "agent/infrastructure/github/adapter.py",
    "agent/infrastructure/openrouter/adapter.py",
    "agent/domain/values.py",
    # The scanner's own source defines the pattern catalogue and the
    # security tests carry synthetic leak samples by design. They legitimately
    # contain secret-shaped strings; demote to soft findings.
    "tests/security/_scanner.py",
    "tests/security/_scanner_cli.py",
    "tests/security/test_no_plaintext_credentials.py",
    "tests/performance/bench_secret_scan.py",
)


@dataclass(frozen=True)
class Finding:
    path: Path
    lineno: int
    pattern: str
    snippet: str


def walk(root: Path) -> Iterator[Path]:
    """Yield every scannable file under ``root``."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in EXCLUDE_FILE_NAMES:
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
            continue
        yield path


def _is_documentation_line(line: str) -> bool:
    lower = line.lower()
    return any(hint in lower for hint in DOC_HINTS)


def _is_documentation_path(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    return rel in PATHS_WITH_DOCUMENTATION


def scan(roots: Iterable[Path], *, repo_root: Path | None = None) -> list[Finding]:
    """Scan every file under ``roots`` for credential patterns.

    Filters at three levels:

    1. Documented paths (``PATHS_WITH_DOCUMENTATION``) — pattern matches
       are downgraded to warnings (still returned but with the
       ``docpath:`` prefix on the pattern name).
    2. Documentation lines (``DOC_HINTS``) — match suppressed.
    3. ``# noqa: secret-scan`` line marker — match suppressed.

    Returns a list of :class:`Finding` instances. Empty list ⇒ all clean.
    """
    repo_root = repo_root or Path.cwd()
    findings: list[Finding] = []
    for root in roots:
        for path in walk(root):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            in_doc_path = _is_documentation_path(path, repo_root)
            # Whole-file pattern: kind: Secret can span lines.
            # Per-line patterns run below.
            for lineno, line in enumerate(text.splitlines(), start=1):
                if LINE_ALLOW_MARKER.search(line):
                    continue
                if _is_documentation_line(line):
                    continue
                for pat_name, pat in PATTERNS.items():
                    if pat.search(line):
                        prefix = "docpath:" if in_doc_path else ""
                        findings.append(
                            Finding(
                                path=path,
                                lineno=lineno,
                                pattern=f"{prefix}{pat_name}",
                                snippet=line.strip()[:200],
                            )
                        )
    return findings


def hard_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Return only findings outside documented paths."""
    return [f for f in findings if not f.pattern.startswith("docpath:")]
