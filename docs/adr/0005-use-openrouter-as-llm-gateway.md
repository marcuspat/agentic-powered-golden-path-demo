# ADR-0005: Use OpenRouter as the LLM gateway

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Agent Engineering
- **Tags:** agent, llm, vendor, openrouter

## Context

The agent must convert a natural-language request — *"I need to deploy my new NodeJS service called inventory-api"* — into a structured `app_name` (`inventory-api`). The extraction is currently a single chat-completion call (`extract_app_name_from_request`, `ai-onboarding-agent/agent.py:133`) with a regex fallback (ADR-0011).

We need an LLM provider that:

- Speaks the OpenAI-compatible chat-completions wire format so the official `openai` SDK works unchanged.
- Lets us swap the underlying model (GPT, Claude, Llama, Mistral) by changing one string.
- Exposes simple per-key billing for demos and workshops.

## Decision Drivers

- Single API key, many models — important for live demos where model availability or pricing changes.
- OpenAI-compatible API surface so we don't ship adapter code.
- Fail-soft: if the gateway is unreachable, the agent must still succeed via the regex fallback (ADR-0011).
- Demonstration-grade reliability; this is not a production decision.

## Considered Options

1. **OpenRouter** — gateway in front of many model providers; OpenAI-compatible.
2. **OpenAI directly** — first-party, fewer model choices, billing per organisation.
3. **Anthropic directly** — first-party Claude; requires a different SDK.
4. **Self-hosted (Ollama, vLLM)** — no SaaS dependency but adds memory/GPU requirements that violate the "Docker-only" promise.
5. **Hybrid: OpenAI primary, OpenRouter secondary** — adds operational complexity for marginal benefit.

## Decision

We will use **OpenRouter** via the `openai` SDK with `base_url="https://openrouter.ai/api/v1"`. The model is parameterised — currently `openai/gpt-3.5-turbo` — and can be swapped without code changes. The API key lives in the `OPENROUTER_API_KEY` environment variable (ADR-0014).

Failures from OpenRouter (network, auth, quota, rate-limit) are caught and the agent falls through to the regex fallback. The user is never blocked by an LLM outage.

## Consequences

### Positive

- One key, many models; suitable for live demos.
- Drop-in `openai` SDK; no extra dependencies.
- Fail-soft path means the demo continues to work offline.

### Negative / Costs

- An additional vendor sits between us and the model provider; latency is slightly higher.
- Per-request pricing varies by model; demos must use a low-cost model.
- OpenRouter outages affect every model; mitigated by the fallback.

### Neutral

- Switching to a different gateway later is a one-line change in the `openai.OpenAI(base_url=…)` call.

## Compliance & Security Considerations

- The user's natural-language request is sent to OpenRouter and onward to the model provider. Do **not** include secrets or PII in requests.
- The `OPENROUTER_API_KEY` is read from the environment; never hard-code it. The README warns demo participants to use their own key.
- Rate-limit and abuse handling is OpenRouter's responsibility; we trust their TLS and their data-handling policy. Production deployments should re-evaluate.

## Follow-up Work

- [ ] Make the model name configurable via `OPENROUTER_MODEL` rather than hard-coded.
- [ ] Add a `--no-llm` flag that skips OpenRouter and exercises the regex path for offline demos.
- [ ] Add structured logging of model, tokens, and latency.

## References

- ADR-0004 — Python implementation.
- ADR-0011 — Regex fallback.
- ADR-0014 — Environment-variable configuration.
- OpenRouter docs: <https://openrouter.ai/docs>.
