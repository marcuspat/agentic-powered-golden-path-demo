# ADR-0004: Use Python for the onboarding agent

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Agent Engineering
- **Tags:** agent, language, ecosystem

## Context

The onboarding agent must call an LLM, talk to GitHub's REST API, drive `git`, render Jinja2 templates, and apply manifests to Kubernetes. It runs as a short-lived CLI invoked from `demo.sh` and from a developer's terminal. The implementation lives in `ai-onboarding-agent/agent.py` and a parallel copy under `src/agent.py`.

The choice of language influences which SDKs, LLM frameworks, and Kubernetes client libraries are first-class, and how readable the agent is to platform engineers — the primary audience for the demo.

## Decision Drivers

- First-class clients for the LLM, GitHub, and Kubernetes APIs.
- Familiarity for the platform engineering audience (Python is the lingua franca of CNOE tooling and SRE).
- Fast iteration; the agent is a demo more than a service.
- Easy templating with Jinja2.
- Low operational overhead; runs as a CLI without a runtime server.

## Considered Options

1. **Python 3.9+** with `openai`, `PyGithub`, `kubernetes`, and `jinja2`.
2. **TypeScript / Node.js** with the official OpenAI SDK and Octokit.
3. **Go** with the Kubernetes client-go and `go-github`.
4. **Rust** for a compiled, redistributable single binary.

## Decision

We will implement the agent in **Python 3.9+**. The dependencies — pinned in `requirements.txt` — are:

- `openai` for the OpenRouter-compatible chat completions client (ADR-0005).
- `PyGithub` for repository creation and metadata.
- `kubernetes` for cluster interactions where `kubectl` is unsuitable.
- `jinja2` for stack template rendering (ADR-0007).
- `langchain-community` reserved for future tool-orchestration upgrades.
- `python-dotenv`, `requests` for plumbing.

The CLI is invoked as `python3 agent.py "<natural-language request>"`. There is no long-lived server.

## Consequences

### Positive

- Mature, well-documented SDKs for every external system the agent touches.
- Readable to the project's audience; aligns with the rest of the CNOE Python ecosystem (e.g. `ai-platform-engineering`).
- Jinja2 is idiomatic for template rendering.
- Trivial packaging: a `requirements.txt` and `python3 agent.py`.

### Negative / Costs

- Cold-start latency from the Python interpreter (~150-300 ms).
- Distribution requires a Python runtime on the user's machine; we cannot ship a single static binary.
- Type discipline must be enforced through reviews; the codebase is not yet typed with `mypy`.

### Neutral

- Two copies of the agent currently live in `ai-onboarding-agent/agent.py` and `src/agent.py`. ADR-0013 makes a decision about the canonical location.

## Compliance & Security Considerations

- `subprocess` is used for `git` and `kubectl`; argument lists must always be passed as Python lists (not shell strings) to avoid command injection. The current implementation generally complies; a future refactor should add a thin wrapper that enforces this.
- LLM input is included verbatim in a prompt; no shell interpolation occurs, but downstream string fields (e.g. `app_name`) must be validated before they enter `git`, `kubectl`, or filesystem paths.
- Pin all dependencies in `requirements.txt` and verify hashes in CI.

## Follow-up Work

- [ ] Add `mypy --strict` to CI.
- [ ] Introduce a `subprocess` wrapper that enforces list-form arguments and logs commands.
- [ ] Decide whether to keep `src/agent.py` or remove it (see ADR-0013).

## References

- ADR-0005 — OpenRouter as the LLM gateway.
- ADR-0007 — Jinja2 for template rendering.
- ADR-0013 — Single-process CLI architecture.
- `requirements.txt` for pinned versions.
