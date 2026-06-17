# ADR 0022 â Dual Agent Architecture: v1 Procedural vs v2 OOP

## Status

Accepted â co-existence, v1 is primary demo agent

## Date

2026-06-16

## Context

The repository contains two agent implementations:

| | `ai-onboarding-agent/agent.py` (v1) | `src/agent.py` (v2) |
|-|-------------------------------------|----------------------|
| Style | Procedural (module-level functions) | OOP (`OnboardingAgent` class) |
| Config | 3 env vars, hardcoded template paths | 5 env vars, configurable template paths |
| LLM client | `openai` lib with OpenRouter base URL | `requests` direct HTTP to OpenRouter |
| Error handling | Basic try/except with warn+fallback | Structured with domain exceptions |
| Kubernetes | `config.load_kube_config()` + kubectl | Same pattern |
| Test coverage | `ai-onboarding-agent/test_agent.py` | `src/test_agent.py` + `src/test_integration.py` |

Both pass CI. v1 is simpler to demo; v2 is more production-capable.

## Decision

Maintain both agents in co-existence:

1. **v1 (`ai-onboarding-agent/agent.py`) is the primary demo agent.** It has fewer env var requirements (no `NODEJS_TEMPLATE_PATH`/`GITOPS_TEMPLATE_PATH` â paths are derived from CWD), making it simpler to bootstrap for live demos. `make demo` uses this agent.

2. **v2 (`src/agent.py`) is the production reference.** It is the canonical, fully-typed, production-grade implementation with comprehensive test coverage and configurable template paths. It's what a platform team would evolve for real environments.

We do NOT consolidate into a single agent. The pedagogical value of showing both a simple working implementation and a production-grade refactor is high for the target audience (platform engineers evaluating the approach).

The co-existence is documented explicitly in the README and via a DDD bounded context boundary: `ai-onboarding-agent/` lives in the **Demo** context; `src/` lives in the **Platform Engineering** context.

## Consequences

**Positive:**
- Demo remains `python3 agent.py "deploy my app"` â 10-second explanation.
- v2 shows what production looks like without replacing what works in demos.
- Both are tested in CI; no dead code.

**Negative / Trade-offs:**
- Two codebases to maintain. New logic (e.g., new LLM extraction strategies) must be ported to both until consolidation.
- New contributors may be confused about which to extend.

## Mitigation

- `README.md` clearly labels both agents and their purpose.
- The `Makefile` is the canonical entry point and always uses v1 for `make demo`.
- `make demo-v2` (future target) can exercise the OOP agent against a running cluster.

## Consolidation Criteria

When the following are all true, consolidate:
1. v2 has feature parity with v1 (same 3-env-var startup, derived template paths)
2. v2 passes the same end-to-end demo flow
3. A real IDP deployment is being targeted (not just demo)

At that point, retire v1 and promote v2 to `agent.py` in the repo root.
