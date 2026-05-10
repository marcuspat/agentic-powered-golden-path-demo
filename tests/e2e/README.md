# Tier 3 — End-to-End

Full-flow tests against a live KinD cluster and live GitHub. Always
skipped unless `RUN_E2E=1` is exported.

## Required environment

| Variable             | Why                                  |
|----------------------|--------------------------------------|
| `RUN_E2E`            | Must equal `1` to opt in             |
| `GITHUB_TOKEN`       | PAT for repo creation (ADR-0014)     |
| `GITHUB_USERNAME`    | Owner namespace for created repos    |
| `OPENROUTER_API_KEY` | LLM access for intent extraction     |
| `KUBECONFIG`         | Optional; defaults to `~/.kube/config` |

## Running

```bash
RUN_E2E=1 \
  GITHUB_TOKEN=... \
  GITHUB_USERNAME=... \
  OPENROUTER_API_KEY=... \
  pytest tests/e2e -q
```

Or via the `Makefile`:

```bash
make test-e2e
```

## CI policy

Per ADR-0015 the E2E tier runs nightly and on `release/*` branches; it
never runs on PRs originating from forks (no secret access).
