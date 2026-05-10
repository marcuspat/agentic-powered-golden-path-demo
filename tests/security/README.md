# Tier 5 — Security

Static and dynamic checks that protect secret hygiene, surface known
CVEs, and assert RBAC posture. Per ADR-0015 SAST and dependency scans
run on every PR; RBAC checks run nightly against a live cluster.

## Files

- `test_no_plaintext_credentials.py` — regex sweep over `cnoe-stacks/`
  and `agent/` for known secret shapes (PATs, OpenAI keys, RSA private
  keys, Bearer tokens, AWS secret-access-key references). Skipped if
  neither directory exists in this checkout.
- `test_dependency_audit.py` — runs `pip-audit` against
  `requirements.txt`. Skipped if `pip-audit` is not installed.
- `test_legacy_security_scan.py` — older comprehensive scanner; marked
  `legacy`.
- A future `test_rbac.py` (per ADR-0015 follow-up work) will exercise
  RBAC against a real cluster; tracked but not yet authored.

## Adding a new pattern

Add the regex to the `_PATTERNS` map in
`test_no_plaintext_credentials.py`. Keep patterns specific (length
floors, character classes) so the scanner does not become noisy. Lines
containing the substrings `example` or `placeholder` (case-insensitive)
are treated as documentation and skipped.

## Required tools

- `pip-audit` for dependency CVE scanning. Install via
  `pip install -r requirements-dev.txt`.
