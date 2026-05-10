# Golden Path Test Suite

This directory implements the **multi-tier testing strategy** described in
[`docs/adr/0015-multi-layer-testing-strategy.md`](../docs/adr/0015-multi-layer-testing-strategy.md).
Every test is filed into exactly one tier; each tier has a name, an owner,
a CI policy, and a wall-clock budget.

## Layout

```
tests/
├── conftest.py            # shared fixtures (env isolation, paths, sample data)
├── unit/                  # Tier 1 — pure functions, no I/O
├── integration/           # Tier 2 — real Jinja2 / git / subprocess; mocked GitHub & OpenRouter
├── e2e/                   # Tier 3 — full flow against live cluster + GitHub
├── performance/           # Tier 4 — benchmarks, regressions only
├── security/              # Tier 5 — secret scans, dep audits, RBAC checks
├── ui/                    # Tier 6 — Playwright (placeholder)
├── README.md              # this file
├── TEST_SUITE_SUMMARY.md  # narrative summary of the suite
├── test_config.json       # static configuration for legacy harness
└── (demo phase scripts; see below)
```

## Tier matrix

| Tier         | Marker        | Runs in CI?                        | Owner                | Budget       |
|--------------|---------------|------------------------------------|----------------------|--------------|
| Unit         | `unit`        | Always                             | Agent Engineering    | < 30 s       |
| Integration  | `integration` | Always                             | Agent Engineering    | < 2 min      |
| E2E          | `e2e`         | Nightly + on `release/*`           | Platform Engineering | < 10 min     |
| Performance  | `performance` | Weekly                             | SRE                  | budget-bound |
| Security     | `security`    | Always (SAST/deps), nightly (RBAC) | Security Engineering | < 5 min      |
| UI           | (Playwright)  | Always when UI exists              | Front-end            | < 3 min      |

The `legacy` marker is applied to the pre-tier tests we migrated; they
are excluded from the default `pytest` run via `make test-unit` and
`make test-integration`. Run them explicitly with
`pytest -m legacy tests/`.

## How to run

```bash
make test-unit           # Tier 1
make test-integration    # Tier 2 (excludes legacy)
make test-e2e            # Tier 3 (sets RUN_E2E=1)
make test-perf           # Tier 4
make test-security       # Tier 5
make test                # Tiers 1 + 2 (the PR gate)
make test-all            # lint + typecheck + test + test-security
```

Direct invocation also works:

```bash
pytest tests/unit -q
pytest tests/integration -q -m "not legacy"
RUN_E2E=1 pytest tests/e2e -q
pytest tests/security -q
```

## Required environment

| Variable             | Used by               | Purpose                                  |
|----------------------|-----------------------|------------------------------------------|
| `RUN_E2E`            | Tier 3                | Must equal `1` to opt in                 |
| `GITHUB_TOKEN`       | Tier 3                | PAT with `repo` scope (ADR-0014)         |
| `GITHUB_USERNAME`    | Tier 3                | Owner namespace for created repos        |
| `OPENROUTER_API_KEY` | Tier 3                | LLM access for intent extraction         |
| `KUBECONFIG`         | Tiers 3 & 5 (RBAC)    | Optional; defaults to `~/.kube/config`   |

`tests/conftest.py` strips these from the process environment for every
test by default so unit and integration tests cannot accidentally rely
on them. E2E tests opt back in by reading `os.environ` directly inside
the test body.

## Demo phase scripts (not part of the tier system)

These pre-date the tier model and are kept in `tests/` for the demo's
phased walk-through. They are not invoked by `make test*` targets.

- `prerequisites_check.sh` — checks Docker, kubectl, etc.
- `test-phase1-prerequisites.sh` — phase-1 system checks.
- `test-phase2-stack-creation.sh` — phase-2 stack template checks.
- `test-phase3-agent-functionality.py` — phase-3 agent CLI checks.
- `validate-demonstration.sh` — full demo go/no-go.
- `run-all-tests.py`, `test_runner.py` — older orchestrators.
- `test_config.json`, `TEST_SUITE_SUMMARY.md` — supporting data.

## Markers

Defined in `pyproject.toml`:

- `unit` — Tier 1
- `integration` — Tier 2
- `e2e` — Tier 3
- `performance` — Tier 4
- `security` — Tier 5
- `legacy` — pre-tier suites that we keep around for safety

## Fixtures

`tests/conftest.py` exports:

- `repo_root` — absolute path to the repo root
- `stack_dir` — `cnoe-stacks/`
- `templates_dir` — `templates/`
- `agent_dir` — `agent/` (may not yet exist)
- `tmp_workspace` — fresh temporary directory under `tmp_path`
- `sample_app_name`, `sample_correlation_uuid` — canonical sample values
- `_isolate_env` (autouse) — strips all known agent env vars before each test

## Adding a new test

1. Decide which tier owns the behaviour. If unsure, ask the
   reviewer-checklist question from `docs/ddd/12-implementation-guide.md`:
   "which layer owns this rule?".
2. Add the test under `tests/<tier>/test_*.py`.
3. Apply the matching marker via
   `pytestmark = pytest.mark.<tier>` (single tier) or a list (cross-tier).
4. If the test depends on the `agent.*` package, gate it with
   `pytest.importorskip("agent.<module>", reason="...")` so collection
   succeeds even when the orchestrator's parallel slice has not yet
   landed the dependency.

## See also

- ADR-0015 — multi-layer testing strategy.
- `docs/ddd/12-implementation-guide.md` — testing patterns by tactical
  construct (value object, aggregate, service, application service,
  adapter, repository).
- `Makefile` at the repo root — canonical entry points.
