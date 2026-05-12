"""Standalone entry point for the credential scanner.

Run via ``python -m tests.security._scanner_cli`` (also wired up as
``make secret-scan``). Exit codes:

- 0 — clean, no hard findings.
- 1 — hard findings; one line per finding printed to stderr.
- 2 — usage error.

Soft findings (matches inside paths listed in
``tests.security._scanner.PATHS_WITH_DOCUMENTATION``) are printed to
stdout as ``[soft]`` but do not affect the exit code.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from tests.security._scanner import (
    Finding,
    hard_findings,
    scan,
)


def _print_findings(findings: List[Finding]) -> None:
    hard = hard_findings(findings)
    soft = [f for f in findings if f.pattern.startswith("docpath:")]
    if soft:
        print(f"# {len(soft)} soft finding(s) inside documented paths:")
        for f in soft:
            print(f"  {f.path}:{f.lineno} [{f.pattern}] {f.snippet}")
    if hard:
        print(f"# {len(hard)} hard finding(s):", file=sys.stderr)
        for f in hard:
            print(f"  {f.path}:{f.lineno} [{f.pattern}] {f.snippet}", file=sys.stderr)


def main(argv: List[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv:
        roots = [Path(a) for a in argv]
    else:
        repo_root = Path(__file__).resolve().parents[2]
        roots = [
            p for p in (repo_root / "cnoe-stacks", repo_root / "agent", repo_root / "config")
            if p.exists()
        ]
        if not roots:
            print("No scan targets found in repo", file=sys.stderr)
            return 2

    repo_root = Path(__file__).resolve().parents[2]
    findings = scan(roots, repo_root=repo_root)
    _print_findings(findings)
    if hard_findings(findings):
        return 1
    print(f"OK — scanned {len(roots)} root(s), no hard findings.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
