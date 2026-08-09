# Release Notes — v1.1.0

**Project:** agentic-powered-golden-path-demo  
**Repository:** https://github.com/adventurewave-labs/agentic-powered-golden-path-demo  
**Release Date:** 2026-06-13  
**Merged PR:** [#1 — docs: add full ADR + DDD documentation set](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo/pull/1)  
**Branch:** `claude/create-adr-ddd-docs-iOd23` → `main`  
**License:** Apache 2.0

---

## Summary

v1.1.0 completes the documentation foundation for the Golden Path AI-powered developer onboarding platform. This release adds a comprehensive Architecture Decision Record (ADR) library, a full Domain-Driven Design (DDD) model, an exhaustively verified validation report, a persona-driven use case guide, and a rewritten README — converting the project from a working prototype into a documented, production-advisable reference implementation.

No application code was changed. All quality gates pass.

---

## What's New

### Architecture Decision Records — 20 ADRs (`docs/adr/`)

Every key design choice is now recorded in Nygard/MADR format with context, decision, rationale, and consequences:

| ADR | Decision |
|-----|----------|
| ADR-0001 | Use idpbuilder for local IDP bootstrapping |
| ADR-0002 | Use ArgoCD as the GitOps controller |
| ADR-0003 | Python as the agent language |
| ADR-0004 | OpenRouter as the LLM gateway |
| ADR-0005 | Two-repository pattern (source + GitOps) |
| ADR-0006 | Jinja2 for stack template rendering |
| ADR-0007 | GitHub as the source control backend |
| ADR-0008 | KinD as the local Kubernetes runtime |
| ADR-0009 | Tekton for CI pipeline execution |
| ADR-0010 | Regex fallback for NLP extraction |
| ADR-0011 | cnoe-stacks for NodeJS templates |
| ADR-0012 | CLI-first architecture (`python -m agent`) |
| ADR-0013 | Environment-variable configuration (no config files) |
| ADR-0014 | Five-tier test pyramid strategy |
| ADR-0015 | `localtest.me` for local ingress resolution |
| ADR-0016 | Namespace isolation per application |
| ADR-0017 | Credential management approach |
| ADR-0018 | Credential management approach (secret handling) |
| ADR-0019 | Rollback strategy via GitOps revert |
| ADR-0020 | Observability approach (structured JSONL events) |

---

### Domain-Driven Design Model — 13 docs + 3 diagrams (`docs/ddd/`)

Strategic, tactical, and application layers fully documented with Mermaid diagrams for context map, aggregate structure, and event flows.

---

## Bug Fixes

| Component | Issue | Fix |
|-----------|-------|-----|
| `Makefile` | `make agent-cli` without `REQUEST` crashes with `unbound variable` under `set -u` | Changed `[ -z "$REQUEST" ]` to `[ -z "${REQUEST:-}" ]` |

---

## Metrics

| Metric | Value |
|--------|-------|
| ADRs added | 20 |
| DDD documents added | 13 |
| Mermaid architecture diagrams | 3 |
| CLI commands validated | 30 |
| Test assertions passing | 156 unit + 11 integration |
| CVEs | 0 |
| Secret scan findings | 0 |
| Bugs found (and fixed) | 1 |

---

## Upgrade Notes

Docs-only release. Drop-in compatible with v1.0.0.

---

## Links

- [Repository](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo)
- [GitHub Release](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo/releases/tag/v1.1.0)
- [PR #1](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo/pull/1)
- [ADR Index](https://github.com/adventurewave-labs/agentic-powered-golden-path-demo/blob/main/docs/adr/README.md)
