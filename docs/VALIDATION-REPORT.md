# Validation Report

**Generated:** 2026-05-23  
**Branch:** `claude/create-adr-ddd-docs-iOd23`  
**Agent version:** 0.2.0  
**Python runtime:** 3.11.15 (CI matrix: 3.9 and 3.12)

This document captures the exact commands run against the repository and their
verbatim outputs. All gate stages are fully automated and reproducible via
`scripts/validate.sh` or `make test-all`.

---

## Environment

```
$ python3 --version
Python 3.11.15

$ python3 -m agent --version
agent 0.2.0
```

---

## CLI Validation

### Help text

```
$ python3 -m agent --help
usage: agent [-h] [--version] [--validate-env] [--log-level LOG_LEVEL]
             {onboard,cleanup} ...

Golden Path AI-powered onboarding agent

positional arguments:
  {onboard,cleanup}
    onboard             Onboard a new application
    cleanup             Tear down an onboarded application

options:
  -h, --help            show this help message and exit
  --version             Print version and exit
  --validate-env        Check required env vars and exit
  --log-level LOG_LEVEL
                        Python logging level (default INFO)
```

### `onboard` subcommand help

```
$ python3 -m agent onboard --help
usage: agent onboard [-h] [--no-llm] [--dry-run] [--actor ACTOR] request

positional arguments:
  request        Natural-language onboarding request

options:
  -h, --help     show this help message and exit
  --no-llm       Skip OpenRouter; use the regex/default extractor
  --dry-run      Parse and validate but do not provision
  --actor ACTOR  Identity of the requester for audit/logs
```

### `cleanup` subcommand help

```
$ python3 -m agent cleanup --help
usage: agent cleanup [-h] [--repos] [--keep-namespace] [--namespace NAMESPACE]
                     [--actor ACTOR]
                     app_name

positional arguments:
  app_name              Application name (DNS-safe slug)

options:
  -h, --help            show this help message and exit
  --repos               Also delete the source + gitops GitHub repositories
  --keep-namespace      Do not delete the Kubernetes namespace
  --namespace NAMESPACE
                        Override the namespace (default: <app-name>)
  --actor ACTOR         Identity of the operator for audit/logs
```

### Environment validation (no credentials)

```
$ python3 -m agent --validate-env
Missing env vars: ['GITHUB_TOKEN', 'GITHUB_USERNAME', 'OPENROUTER_API_KEY']
exit code: 2
```

Expected: exits `2` when required variables are absent.

### Dry-run onboarding (no external calls)

```
$ python3 -m agent onboard "deploy my nodejs service called inventory-api" \
    --dry-run --no-llm
2026-05-23 16:38:12,217 WARNING agent.application.onboarding onboarding.dry_run \
    command=OnboardingCommand(request_text='deploy my nodejs service called inventory-api', \
    actor=ActorIdentity(value='developer@local'), \
    options=OnboardingOptions(dry_run=True, force_recreate=False))
⚠️  Onboarding cancelled
   reason: dry_run
exit code: 2
```

Expected: exits `2` (cancelled). Intent extraction and validation run; no
GitHub, Git, or Kubernetes calls are made.

---

## Gate Stage: Lint

```
$ make lint
python3 -m ruff check agent/ tests/
All checks passed!
```

**Result: PASS** — 0 ruff violations across `agent/` (42 source files) and `tests/`.

---

## Gate Stage: Typecheck

```
$ make typecheck
python3 -m mypy agent/
Success: no issues found in 42 source files
```

**Result: PASS** — mypy strict-ish configuration (see `[tool.mypy]` in
`pyproject.toml`). All 42 agent source files typed cleanly.

---

## Gate Stage: Unit + Integration Tests

```
$ make test
python3 -m pytest tests/unit tests/integration -q -m "not legacy"
........................................................................
........................................................................
............
156 passed, 1 warning in 0.35s
```

The 1 warning is a benign pytest collection notice about a non-test class named
`TestResult` in the legacy integration suite (excluded by the `not legacy` mark).

**Result: PASS** — 156 tests, 0 failures.

### Test distribution

| Module | Tests |
|---|---|
| `tests/unit/` | ~145 |
| `tests/integration/` | ~11 |

---

## Gate Stage: Security Tests

```
$ make test-security
python3 -m pytest tests/security -q
...................
19 passed in 13.94s
```

**Result: PASS** — 19 security tests covering:

| Test file | Coverage |
|---|---|
| `test_no_plaintext_credentials.py` | Credential leak detection in committed tree |
| `test_dependency_audit.py` | `pip-audit` CVE scan with documented ignore list |
| `test_legacy_security_scan.py` | Legacy scanner regression suite |

### Dependency audit detail

```
$ pip-audit -r requirements.txt
No known vulnerabilities found
```

Two advisories are documented in `IGNORED_VULN_IDS` within
`tests/security/test_dependency_audit.py` and excluded with `--ignore-vuln`:

| ID | Package | Reason for exclusion |
|---|---|---|
| `PYSEC-2024-278` | langchain-community | TFIDFRetriever SSRF — code path unused in this project; no patched version available |
| `PYSEC-2025-183` | PyJWT (transitive via PyGithub) | Disputed key-length advisory; no patched version available |

---

## Gate Stage: Secret Scan

```
$ make secret-scan
python3 -m tests.security._scanner_cli
OK — scanned 3 root(s), no hard findings.
```

**Result: PASS** — scanner checked `agent/`, `cnoe-stacks/`, and `tests/` for
hardcoded credentials. No hard findings. Files that legitimately contain
credential-shaped strings by design (the scanner's own test fixtures) are listed
in `PATHS_WITH_DOCUMENTATION` and produce soft (informational) findings only.

---

## Gate Stage: Performance Tests

```
$ make test-perf
python3 -m pytest tests/performance -q
...........
11 passed, 1 skipped in 0.66s

SKIPPED [1] tests/performance/test_legacy_performance.py:14: legacy perf suite needs psutil
```

**Result: PASS** — 11 benchmarks passed. The 1 skip is the legacy perf suite
which requires `psutil`; it is excluded by default from the CI gate.

---

## Full Validation Gauntlet

```
$ scripts/validate.sh
== lint ==
All checks passed!
OK: lint
== typecheck ==
Success: no issues found in 42 source files
OK: typecheck
== unit ==
........................................................................
........................................................................
.
OK: unit
== integration ==
...........
OK: integration
== security ==
...................
OK: security

All validations passed.
```

**Result: PASS** — all five stages complete without error.

---

## Summary

| Gate | Command | Result | Notes |
|---|---|---|---|
| Lint | `make lint` | PASS | 0 ruff violations |
| Typecheck | `make typecheck` | PASS | 42 files, 0 mypy issues |
| Unit + Integration | `make test` | PASS | 156 passed |
| Security | `make test-security` | PASS | 19 passed; 2 CVEs documented and excluded |
| Secret scan | `make secret-scan` | PASS | No hard findings |
| Performance | `make test-perf` | PASS | 11 passed, 1 skipped (psutil) |
| Dependency audit | `pip-audit` | PASS | No hard vulnerabilities |
| Full gauntlet | `scripts/validate.sh` | PASS | All stages |

---

## Known Gaps

The one category not captured above is the **end-to-end (Tier 3) suite**,
which requires a live KinD cluster, GitHub credentials, and OpenRouter access:

```bash
# Not run as part of the automated gate
RUN_E2E=1 make test-e2e
```

This tier is intentionally excluded from CI because it creates real GitHub
repositories and Kubernetes resources. It must be run manually in an environment
with the required infrastructure before any live-traffic deployment.
