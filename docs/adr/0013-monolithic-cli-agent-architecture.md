# ADR-0013: Ship the agent as a single-process CLI

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Agent Engineering
- **Tags:** agent, architecture, cli

## Context

The agent has three tools — `create_github_repo()`, `populate_repo_from_stack()`, `create_argocd_application()` — orchestrated by `run_onboarding_flow()`. It is invoked once per developer request and exits when the flow finishes (or fails). Two equivalent copies live in `ai-onboarding-agent/agent.py` and `src/agent.py`.

We must decide whether the agent should:

- Stay as a single Python file invoked via CLI;
- Become a long-running HTTP service that exposes an `/onboard` endpoint;
- Decompose into separate microservices (LLM, GitHub, GitOps);
- Be packaged as a container image.

## Decision Drivers

- The agent is a demo first, a service second; the CLI shape is what audiences see.
- Operational simplicity: a CLI has no uptime, no scaling, no load balancer.
- Existing entry points (`demo.sh`, `interactive-demo.sh`) call `python3 agent.py "<request>"`.
- Future evolution to a server (e.g. Slack bot, web UI front-end) should be feasible without a rewrite.

## Considered Options

1. **Single-file CLI** in Python, invoked per request.
2. **HTTP service** exposing `/onboard` (FastAPI), with the same orchestration logic.
3. **Microservices**: a thin CLI/HTTP front-end and three backend tool services.
4. **Containerised CLI** distributed via OCI image.

## Decision

We will keep the agent as a **single-file Python CLI** for the foreseeable future. The structure will be tightened so that:

- The orchestration (`run_onboarding_flow`) is separated from I/O (CLI parsing, exit codes).
- Each tool is a top-level function with explicit dependencies, so a future HTTP front-end can call it without re-architecture.
- `ai-onboarding-agent/agent.py` is the canonical implementation; `src/agent.py` is removed in a follow-up cleanup.

A future ADR will introduce a server profile when there is a concrete need (Slack bot, multi-tenant UI). Until then, *one Python file, three tools, one `run_onboarding_flow`*.

## Consequences

### Positive

- Zero operational overhead; nothing to deploy or babysit.
- Easy to read in a workshop; the entire agent fits on a screen.
- Each tool is independently testable.

### Negative / Costs

- No HTTP surface; consumers must shell out.
- Cold-start cost (Python interpreter + imports) on every invocation.
- Two-file duplication today (`src/` vs. `ai-onboarding-agent/`) is a code-smell to remove.

### Neutral

- The choice can be revisited cheaply because each tool is a pure function over its inputs.

## Compliance & Security Considerations

- A CLI has no inbound network surface; an attacker would need shell access to the developer's workstation. This is the right posture for a local demo.
- A future HTTP profile **must** add authentication, rate limiting, and audit logging before exposure.

## Follow-up Work

- [ ] Remove `src/agent.py` and update tests to import from `ai-onboarding-agent/agent.py` (or move to `agent/` package).
- [ ] Refactor into `agent/{cli.py, tools/, orchestration.py}` so the HTTP profile is a future drop-in.
- [ ] Document a "server profile" ADR if/when a Slack or web entry point is needed.

## References

- ADR-0004 — Python language choice.
- ADR-0014 — Environment-variable configuration.
- DDD: *Onboarding Orchestration* application service.
