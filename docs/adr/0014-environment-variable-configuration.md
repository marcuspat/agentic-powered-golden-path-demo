# ADR-0014: Configure the agent through environment variables

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Agent Engineering, Platform Engineering
- **Tags:** configuration, secrets, agent

## Context

The agent needs three secrets and several knobs:

- `GITHUB_TOKEN` (secret, required) — PAT for repository creation.
- `GITHUB_USERNAME` (required) — namespace for repository creation.
- `OPENROUTER_API_KEY` (secret, required) — LLM access.
- `KUBECONFIG` (optional) — path to the kubeconfig used by the `kubernetes` library and `kubectl`.

We must decide where these values live. The choice affects developer ergonomics, secret hygiene, container portability, and CI integration.

## Decision Drivers

- Twelve-Factor compatibility; environment variables are the lingua franca of configuration.
- No secrets in the repository; `.env.example` documents what is needed without committing values.
- Easy to pass into Docker/Kubernetes runtimes if the agent is ever wrapped.
- No bespoke config file format to learn.

## Considered Options

1. **Environment variables** with `.env.example` documentation.
2. **TOML/YAML config file** under `~/.config/golden-path/`.
3. **CLI flags** for everything (`--github-token …`).
4. **Cloud secret manager (AWS SM, Vault)** at runtime.

## Decision

We will use **environment variables** as the sole configuration channel. `.env.example` (in `ai-onboarding-agent/`) lists every variable with a comment explaining purpose and required scope. Developers may use `direnv`, `dotenv`, or shell exports.

The agent validates required variables at startup (`agent.py:230`) and exits non-zero with a clear message if any are missing. Optional variables fall back to library defaults.

| Variable             | Required | Purpose                                                            |
|----------------------|----------|--------------------------------------------------------------------|
| `GITHUB_TOKEN`       | yes      | GitHub PAT with `repo` scope                                       |
| `GITHUB_USERNAME`    | yes      | GitHub user/org that owns onboarded repositories                   |
| `OPENROUTER_API_KEY` | yes      | OpenRouter API key for LLM extraction                              |
| `OPENROUTER_MODEL`   | no       | Override the default model (`openai/gpt-3.5-turbo`)                |
| `KUBECONFIG`         | no       | Override default `~/.kube/config`                                  |
| `STACK_DIR`          | no       | Override the default `cnoe-stacks/` location                       |
| `LOG_LEVEL`          | no       | `INFO` (default) or `DEBUG`                                        |

CLI flags exist only for the natural-language request (`python3 agent.py "<request>"`), which is the *what to do*, not the *how to authenticate*.

## Consequences

### Positive

- Twelve-factor; portable to containers, CI, and Kubernetes secrets.
- No bespoke parser; the standard library suffices.
- Consistent with `kubectl` and most CNCF tools.

### Negative / Costs

- Easy to leak via a `printenv` in a public terminal; demo presenters must take care.
- Multi-environment switching (dev vs. demo vs. prod) requires `direnv` or shell discipline.

### Neutral

- A future config file could augment, not replace, environment variables (env vars always win).

## Compliance & Security Considerations

- `.env` files **must not** be committed; `.gitignore` includes `.env`.
- Logs **must not** echo secret variables; the agent's `logging` configuration writes only the variable names that are missing, never values.
- For containerised use, prefer Kubernetes Secrets mounted as env vars (see ADR-0018).
- Rotate `GITHUB_TOKEN` and `OPENROUTER_API_KEY` regularly; both are read once at startup, so rotation requires a restart.

## Follow-up Work

- [ ] Add a `--validate-env` flag that performs the startup check without running the flow.
- [ ] Surface `OPENROUTER_MODEL` and `STACK_DIR` overrides (currently TODO in code).
- [ ] Document direnv usage in the README.

## References

- ADR-0008 — GitHub PAT scope.
- ADR-0018 — Secret management approach.
- The Twelve-Factor App, "III. Config".
