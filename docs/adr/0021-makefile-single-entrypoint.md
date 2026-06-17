# ADR 0021 â Makefile as Single Developer Experience Entry Point

## Status

Accepted

## Date

2026-06-16

## Context

The repository has a functional AI-powered platform onboarding agent, idpbuilder bootstrap, ArgoCD GitOps templates, and demo scripts. However there is no single, discoverable entry point for a developer cloning the repo for the first time.

The README lists multiple distinct steps across different directories:
- `pip install -r requirements.txt` (no root-level file)
- `./idpbuilder create` (binary must exist/be downloaded)
- `cd ai-onboarding-agent && bash demo.sh demo`

This friction raises the time-to-first-success, especially for conference demos and evaluators.

## Decision

We introduce a `Makefile` at the repository root as the canonical, self-documenting entry point for all developer tasks. Every human-facing workflow (setup, bootstrap, demo, test, teardown) is expressed as a named Make target with a `##` help comment, so `make help` is the only command a new developer needs to memorise.

The Makefile acts as an orchestration shim â it delegates to `scripts/setup.sh`, idpbuilder, and existing demo scripts rather than duplicating logic. This keeps targets thin and the actual shell logic in versioned, testable scripts.

## Consequences

**Positive:**
- `make help` surfaces the full capability of the platform in one command.
- `make demo` is a single command that takes a cold clone to a live ArgoCD-deployed application.
- Make is ubiquitous on macOS and Linux; no additional tooling required.
- Targets are composable: `make setup bootstrap demo` chains into a full onboarding in one line.
- Self-documenting: the Makefile IS the quickstart guide for power users.

**Negative / Trade-offs:**
- Make is not idiomatic for Python projects; some Python developers expect `pip` + script invocations.
- Windows users without WSL2 cannot use Make natively (out of scope for this demo target audience).
- Makefile complexity must be kept minimal â logic belongs in `scripts/`, not in recipe bodies.

## Alternatives Considered

| Option | Rejected Because |
|--------|-----------------|
| `justfile` (Just task runner) | Requires extra install; less universal than Make |
| `Taskfile.yml` | Same issue; adds a tool dependency |
| `pyproject.toml` scripts | Python-only; cannot orchestrate shell/kubectl/idpbuilder |
| Shell script `run.sh` | No built-in help system, no tab-completion in CI systems |

## Implementation

See root `Makefile`. Targets: `help`, `setup`, `bootstrap`, `demo`, `test`, `clean`, `status`.
