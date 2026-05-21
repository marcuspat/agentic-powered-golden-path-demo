"""Scan the repo for plaintext credentials.

The shared scanner (``tests/security/_scanner.py``) defines the pattern
catalogue and walker. This module wires it to three scan targets:

1. **Live source tree** — ``cnoe-stacks/`` and ``agent/`` as they live in the
   checkout. Catches anything a developer might have pasted while editing.
2. **Rendered templates** — every stack template rendered with a realistic
   variable bag into a temp dir. Catches secrets that hide in the template
   but are only visible *after* substitution.
3. **Committed tree** — ``git ls-files`` output filtered through the same
   scanner. Catches anything that slipped past ``.gitignore``.

The scanner classifies hits into:

- *Hard findings* — outside documented paths. **Fail.**
- *Soft findings* — inside documented paths (ADRs, READMEs, templates that
  *describe* credentials). Logged, not failed, so authors can still write
  "Bearer <token>" in a doc without breaking CI.

A test author can opt out a specific line with ``# noqa: secret-scan``.

See ADR-0014 (env-var configuration) and ADR-0018 (credential management).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

scanner = pytest.importorskip(
    "tests.security._scanner",
    reason="scanner helpers not yet landed",
)

Finding = scanner.Finding
scan = scanner.scan
hard_findings = scanner.hard_findings

pytestmark = pytest.mark.security


# ---------------------------------------------------------------------------
# 1. Live source tree
# ---------------------------------------------------------------------------


def test_no_plaintext_credentials_in_live_source_tree(repo_root: Path) -> None:
    targets = [p for p in (repo_root / "cnoe-stacks", repo_root / "agent") if p.exists()]
    if not targets:
        pytest.skip("Neither cnoe-stacks/ nor agent/ exists in this checkout")
    findings = scan(targets, repo_root=repo_root)
    hard = hard_findings(findings)
    if hard:
        msg = ["Plaintext credential candidates in source tree:"]
        for f in hard:
            msg.append(f"  {f.path}:{f.lineno} [{f.pattern}] {f.snippet}")
        pytest.fail("\n".join(msg))


# ---------------------------------------------------------------------------
# 2. Rendered templates
# ---------------------------------------------------------------------------


@pytest.fixture
def rendered_stack(tmp_path: Path, repo_root: Path) -> Path:
    """Render every stack template into a temp dir using the agent's renderer.

    This catches secrets that only appear *after* Jinja2 substitution — e.g.
    a template that did ``token: "{{ token }}"`` where ``token`` is a
    plaintext value rather than an ExternalSecret reference.
    """
    template = pytest.importorskip(
        "agent.domain.services.template_rendering",
        reason="template renderer not landed",
    )
    pytest.importorskip(
        "agent.domain.values", reason="agent.domain.values not landed"
    )

    renderer = template.TemplateRenderingService()
    variables = {
        "appName": "rendered-test",
        "description": "Security scan rendered fixture",
        "namespace": "rendered-test",
        "host": "rendered-test.cnoe.localtest.me",
        "replicas": 2,
        "image": "ghcr.io/cnoe-io/nodejs-hello:latest",
        "gitopsRepoUrl": "https://github.com/example/rendered-test-gitops.git",
    }
    out = tmp_path / "rendered"
    out.mkdir()
    stack_root = repo_root / "cnoe-stacks"
    if not stack_root.exists():
        pytest.skip("cnoe-stacks/ not present")

    for tpl_dir in sorted(p for p in stack_root.iterdir() if p.is_dir()):
        dest = out / tpl_dir.name
        dest.mkdir()
        for rendered in renderer.render(tpl_dir, variables):
            relpath, content = rendered.relative_path, rendered.content
            target = dest / relpath
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return out


def test_no_plaintext_credentials_in_rendered_templates(
    rendered_stack: Path, repo_root: Path
) -> None:
    findings = scan([rendered_stack], repo_root=repo_root)
    hard = hard_findings(findings)
    if hard:
        msg = ["Plaintext credential candidates in *rendered* templates:"]
        for f in hard:
            msg.append(f"  {f.path}:{f.lineno} [{f.pattern}] {f.snippet}")
        pytest.fail("\n".join(msg))


# ---------------------------------------------------------------------------
# 3. Committed tree (git ls-files)
# ---------------------------------------------------------------------------


def _git_tracked_files(repo_root: Path) -> list[Path]:
    if shutil.which("git") is None:
        return []
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=False, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return []
    return [
        repo_root / name
        for name in proc.stdout.split("\0")
        if name and not name.startswith(("idpbuilder-source/", "ai-platform-engineering/"))
    ]


def test_no_plaintext_credentials_in_committed_tree(repo_root: Path) -> None:
    """Last-line defence: scan whatever git would push."""
    tracked = _git_tracked_files(repo_root)
    if not tracked:
        pytest.skip("git not available or no files tracked")

    # Reuse the per-file scanner against the explicit file list rather than
    # the recursive walker, since git already enumerates the universe.
    from tests.security._scanner import (
        DOC_HINTS,
        LINE_ALLOW_MARKER,
        PATTERNS,
        Finding,
        _is_documentation_path,
    )

    findings: list[Finding] = []
    for path in tracked:
        if not path.is_file():
            continue
        if path.suffix in scanner.EXCLUDE_SUFFIXES:
            continue
        if path.name in scanner.EXCLUDE_FILE_NAMES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        in_doc_path = _is_documentation_path(path, repo_root)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if LINE_ALLOW_MARKER.search(line):
                continue
            lower = line.lower()
            if any(hint in lower for hint in DOC_HINTS):
                continue
            for pat_name, pat in PATTERNS.items():
                if pat.search(line):
                    findings.append(
                        Finding(
                            path=path,
                            lineno=lineno,
                            pattern=("docpath:" if in_doc_path else "") + pat_name,
                            snippet=line.strip()[:200],
                        )
                    )
    hard = hard_findings(findings)
    if hard:
        msg = ["Plaintext credential candidates in *committed* tree:"]
        for f in hard:
            msg.append(f"  {f.path}:{f.lineno} [{f.pattern}] {f.snippet}")
        pytest.fail("\n".join(msg))


# ---------------------------------------------------------------------------
# 4. Sanity: the scanner itself catches known shapes
# ---------------------------------------------------------------------------


_SAMPLE_LEAKS = {
    "github_classic_pat": "AUTH_TOKEN=ghp_" + "A" * 36,
    "github_fine_pat": "TOKEN=github_pat_" + "1" * 82,
    "openai_or_openrouter_key": 'OPENROUTER_API_KEY="sk-' + "a" * 32 + '"',
    "openrouter_v1_key": 'KEY="sk-or-v1-' + "f" * 32 + '"',
    # Synthetic 20-char AWS key; canonical AKIAIOSFODNN7EXAMPLE would trip the
    # "example" doc-hint filter (which is exactly what we want for real docs).
    "aws_access_key_id": "AKIAQWERTYUIOPASDFGH",
    "bearer_token": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123",
    "rsa_private_key": "-----BEGIN RSA PRIVATE KEY-----",
    "openssh_private_key": "-----BEGIN OPENSSH PRIVATE KEY-----",
    "slack_token": "xoxb-12345-abcdefghij-1234567",
    "password_literal": 'password: "verylongsecretpassword"',
    "generic_secret_assignment": 'secret: "averyverylongvalue1234567890ab"',
    "k8s_secret_data": "kind: Secret",
    "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
}


@pytest.mark.parametrize("pattern,line", list(_SAMPLE_LEAKS.items()))
def test_scanner_catches_known_leak_shapes(
    tmp_path: Path, pattern: str, line: str
) -> None:
    """Self-check: every pattern in the catalogue catches a synthetic leak."""
    bad = tmp_path / "leak.txt"
    bad.write_text(line + "\n")
    findings = scan([tmp_path], repo_root=tmp_path)
    pattern_names = {f.pattern.removeprefix("docpath:") for f in findings}
    assert pattern in pattern_names, (
        f"pattern {pattern!r} did not fire on {line!r}; got {pattern_names}"
    )


def test_doc_hint_suppresses_match(tmp_path: Path) -> None:
    bad = tmp_path / "doc.md"
    bad.write_text("Example: AUTH=ghp_" + "A" * 36 + " (your-token here)\n")
    findings = scan([tmp_path], repo_root=tmp_path)
    assert hard_findings(findings) == []


def test_noqa_marker_suppresses_match(tmp_path: Path) -> None:
    bad = tmp_path / "marked.py"
    bad.write_text(
        'AUTH = "ghp_' + "A" * 36 + '"  # noqa: secret-scan\n'
    )
    findings = scan([tmp_path], repo_root=tmp_path)
    assert hard_findings(findings) == []
