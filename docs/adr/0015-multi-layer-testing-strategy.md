# ADR-0015: Adopt a layered, multi-tier testing strategy

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Quality Engineering, Agent Engineering
- **Tags:** testing, ci, quality

## Context

The repository contains tests at multiple levels:

- `ai-onboarding-agent/test_agent.py` — unit tests for the agent.
- `src/test_agent.py`, `src/test_integration.py` — alternative/integration tests.
- `tests/golden_path_tests.py`, `tests/test-integration-e2e.py`, `tests/performance_tests.py`, `tests/security_scan.py`, `tests/test-failure-modes.sh` — end-to-end, performance, security, and failure-mode coverage.
- `tests/example.spec.ts` and `playwright.config.ts` — UI tests with Playwright.
- `tests/test-phase[1-3]*.sh` — phased pre-flight checks.

This sprawl is intentional but unstructured; we need an explicit testing strategy that says which layer owns which behaviour, what runs in CI, and what runs only locally.

## Decision Drivers

- Fast feedback for small changes (unit tests in seconds).
- Reliable CI signal that catches integration regressions (mocked external services).
- A demo-grade end-to-end suite that proves the full flow on a real cluster.
- Security and performance concerns must have their own dedicated suites.
- Single command to run "the right tests for this change".

## Considered Options

1. **Test pyramid** — many unit, fewer integration, few E2E. Industry default.
2. **Test honeycomb** — emphasis on integration, sparse unit, sparse E2E.
3. **Single E2E suite** — high confidence, slow feedback, brittle.

## Decision

We will adopt a **test pyramid with explicit tiers**, each with a name, owner, and CI policy. Every test in the repository is filed into one tier. The directory layout settles to:

```
tests/
├── unit/            # Tier 1 — pure functions, mocks for I/O
├── integration/     # Tier 2 — real subprocess/Jinja2/Git but mocked GitHub & OpenRouter
├── e2e/             # Tier 3 — full flow against a live KinD cluster + GitHub
├── performance/     # Tier 4 — measures latency budgets
├── security/        # Tier 5 — secret leak, dependency vulnerabilities, RBAC
└── ui/              # Tier 6 — Playwright tests for any future web UI
```

| Tier            | Runs in CI? | Owner               | Budget          |
|-----------------|-------------|---------------------|-----------------|
| Unit            | Always      | Agent Engineering   | < 30 s          |
| Integration     | Always      | Agent Engineering   | < 2 min         |
| E2E             | Nightly + on `release/*` branches | Platform Engineering | < 10 min |
| Performance     | Weekly      | SRE                 | budget-bound    |
| Security        | Always (SAST + deps), nightly (RBAC) | Security Engineering | < 5 min |
| UI              | Always (when UI exists) | Front-end Engineering | < 3 min |

A `make test`, `make test-integration`, `make test-e2e`, `make test-perf`, `make test-security` set of targets standardises invocation. The phased scripts (`tests/test-phase*.sh`) become tier-specific entry points.

## Consequences

### Positive

- Clear ownership; reviewers know which tier a regression belongs in.
- Fast feedback loop on day-to-day work (unit + integration in CI on every PR).
- Heavy suites do not block PRs but still gate releases.
- A single source of truth for "how do I test X?".

### Negative / Costs

- Migration effort to refile existing scattered tests into the canonical structure.
- Some duplication during transition (unit tests in `ai-onboarding-agent/test_agent.py` mirror what should live in `tests/unit/`).

### Neutral

- The `src/` duplicate copies of agent and tests are slated for removal (see ADR-0013).

## Compliance & Security Considerations

- The security tier owns:
  - `tests/security_scan.py` — SAST and dependency CVE scanning.
  - A new `tests/security/test_secret_leak.py` to assert no secrets reach the GitHub repos created by the agent.
  - A new `tests/security/test_rbac.py` exercised against a real cluster nightly.
- E2E tests require live credentials; they run from a CI environment with secrets injected via the runner's secret store, never from PRs originating in forks.

## Follow-up Work

- [ ] Refile existing tests into `tests/{unit,integration,e2e,performance,security,ui}/`.
- [ ] Add `Makefile` targets and document them in the README.
- [ ] Add coverage gates (e.g. `pytest --cov` minimum 70 % at unit + integration).
- [ ] Author `tests/security/test_secret_leak.py` and `test_rbac.py`.

## References

- `docs/testing-strategy.md` — older strategy doc to be reconciled with this ADR.
- ADR-0013 — single-file CLI (drives unit-test patterns).
- ADR-0018 — secret handling (drives security tests).
