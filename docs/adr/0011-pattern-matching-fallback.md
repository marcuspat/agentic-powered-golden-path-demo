# ADR-0011: Provide a regex fallback for app-name extraction

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Agent Engineering
- **Tags:** agent, llm, resilience, fallback

## Context

`extract_app_name_from_request()` (`agent.py:133`) calls OpenRouter (ADR-0005) to convert a sentence into a slug. The LLM call can fail for several reasons: network outage, expired API key, rate limit, content filtering, or simply the model returning a malformed response. A demo audience does not tolerate the agent halting because a third-party API is unavailable.

The function therefore tries the LLM first, then falls through to a list of regex patterns, then to a hard-coded default of `my-app`.

## Decision Drivers

- Demo-grade resilience: the agent must finish its work even when offline.
- Determinism for testing: the fallback path is fully deterministic.
- Single source of truth for the slug rules; both the LLM prompt and the regex patterns must produce a slug that satisfies the same constraints (lowercase, hyphens only, no leading/trailing dashes).

## Considered Options

1. **LLM with regex fallback** (current implementation).
2. **Regex only** — eliminates the LLM dependency at the cost of natural-language nuance.
3. **LLM only** — fails hard when the gateway is unreachable.
4. **LLM with a second LLM provider as fallback** — adds another vendor to the trust boundary for marginal benefit.

## Decision

We will keep the **LLM-then-regex-then-default** chain. The implementation is:

1. Call OpenRouter (`openai/gpt-3.5-turbo`) and post-process the result with a slug-normalising regex (`[^a-z0-9-]` removed, runs of `-` collapsed, leading/trailing `-` trimmed).
2. On any exception or empty result, run an ordered list of patterns:
   - `called <name>`
   - `named <name>`
   - `<name> service`
   - `<name> app`
   - `deploy <name>`
   - `create <name>`
3. If no pattern matches, return `my-app`.

The `my-app` default is intentional: it lets the demo run end-to-end with a generic request like *"Set me up with something"*, even though the resulting application is named generically.

## Consequences

### Positive

- The agent never aborts because of an LLM failure.
- Tests can pin behaviour by stubbing the LLM and exercising the regex path.
- Slug rules are encapsulated in the function and apply to both paths.

### Negative / Costs

- The regex catalogue is a small parallel grammar to maintain alongside the LLM prompt.
- The default `my-app` can mask broken inputs in production usage; for that we should require a non-default match.

### Neutral

- The fallback ordering is documented in the function docstring and reflected in tests.

## Compliance & Security Considerations

- Regex extraction operates on user-supplied text. Patterns capture only `[a-zA-Z0-9-]`, eliminating shell metacharacters before the slug ever reaches `git`, `kubectl`, or filesystem paths.
- The slug normalisation step is the canonical sanitiser for app names; any new pathway that accepts an app name must invoke it.

## Follow-up Work

- [ ] Refactor the slug normalisation into a `sanitise_app_name(raw: str) -> str` helper used by both code paths.
- [ ] Add an explicit `--strict` mode that errors out instead of falling back to `my-app`.
- [ ] Add tests for each regex pattern in `tests/golden_path_tests.py`.

## References

- ADR-0005 — OpenRouter as LLM gateway.
- ADR-0015 — Multi-layer testing strategy (covers both paths).
- DDD: `AppName` value object, *Onboarding* bounded context.
