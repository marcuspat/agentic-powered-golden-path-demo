# ADR-0001: Record architecture decisions

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering, Architecture Guild
- **Tags:** governance, documentation, process

## Context

The Golden Path AI-Powered Developer Onboarding project spans several technologies — a Python LLM agent, GitHub APIs, idpbuilder, KinD, ArgoCD, Tekton, Jinja2 templates, and a multi-tier test harness. Without an explicit decision log, the *why* of those choices lives only in chat history and the heads of the original contributors. New maintainers re-litigate settled questions, reviewers cannot tell whether a change contradicts a prior decision, and demo audiences see no chain of reasoning behind the architecture.

We need a lightweight, version-controlled record of significant architectural choices that lives next to the code, evolves with it, and is searchable from the repository.

## Decision Drivers

- The decision log must live in the same repository as the code so that pull requests can update both atomically.
- The format must be lightweight enough that contributors actually use it.
- Records must be human-readable as plain Markdown and renderable on GitHub without tooling.
- The format must accommodate decisions about platform infrastructure, agent design, and process.

## Considered Options

1. **Adopt Michael Nygard-style ADRs** stored as Markdown under `docs/adr/`.
2. **Use a wiki** (Confluence, GitHub Wiki) detached from the source tree.
3. **Embed rationale in code comments and READMEs** with no central index.
4. **Use a richer format** (e.g. Y-statements, MADR full template, RFCs).

## Decision

We will adopt **Michael Nygard-style ADRs** with mild MADR influences (decision drivers, explicit consequences split positive/negative, security section), stored under `docs/adr/` as numbered Markdown files.

Records are immutable once accepted. Changes require a new ADR that supersedes the old one. A status of *Proposed*, *Accepted*, *Deprecated*, or *Superseded by ADR-NNNN* is mandatory. A central index in [`README.md`](./README.md) lists every record and its current status.

## Consequences

### Positive

- A single, version-controlled source of truth for architectural intent.
- Reviewers can challenge or cite decisions in pull requests.
- New contributors can read the log front-to-back to understand the system.
- Decisions and code evolve atomically.

### Negative / Costs

- Contributors must remember to write an ADR for substantive changes.
- The log grows over time; navigating older entries requires the index.

### Neutral

- ADRs are not a substitute for runbooks, API docs, or tutorials; those continue to live in their own files.

## Compliance & Security Considerations

Security-relevant choices (secret handling, RBAC, supply chain) must be captured here so that auditors have a single place to look. Each ADR template includes a *Compliance & Security Considerations* section.

## Follow-up Work

- [x] Create `docs/adr/template.md`.
- [x] Create the index in `docs/adr/README.md`.
- [ ] Add a CONTRIBUTING note instructing reviewers to request an ADR for architectural changes.

## References

- Michael Nygard, *Documenting Architecture Decisions* (2011).
- MADR — <https://adr.github.io/madr/>.
- ThoughtWorks Tech Radar entry on Lightweight Architecture Decision Records.
