# ADR-0012: Use cnoe-stacks templates as golden paths

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** templates, stacks, cnoe, golden-path

## Context

A "Golden Path" is a paved, opinionated route from idea to running service. The opinions are encoded as **stack templates**: a directory of files that, when rendered with per-application variables, produces the artefacts a service needs in two repositories (ADR-0006). Today the project has two stacks:

- `cnoe-stacks/nodejs-template/` — the source-side stack (contains `app-source/` with `index.js`, `package.json`, `Dockerfile`, `README.md`).
- `cnoe-stacks/nodejs-gitops-template/` — the GitOps-side stack (`deployment.yaml`, `service.yaml`, `ingress.yaml`).

A duplicate, slightly richer set lives under `templates/` (`nodejs-app-template/`, `nodejs-gitops-template/` with `kustomization.yaml`, `configmap.yaml`). We need a single canonical location and an explicit contract for how a stack is structured, named, and discovered by the agent.

## Decision Drivers

- One canonical location avoids drift between two parallel template sets.
- Stacks must be self-describing so the agent can pick the right template for a request.
- Aligned with the upstream `cnoe-io/stacks` repository naming convention so we can adopt or contribute back.
- Easy to add a new language (Python, Go) by dropping in a new directory.

## Considered Options

1. **Keep `cnoe-stacks/` only**, retire `templates/`.
2. **Keep `templates/` only**, retire `cnoe-stacks/`.
3. **Maintain both**, treating one as a "richer" variant.
4. **Pull stacks at runtime from `cnoe-io/stacks`** instead of vendoring them.

## Decision

We will **keep `cnoe-stacks/` as the canonical location** and treat `templates/` as a deprecated copy slated for removal in a follow-up cleanup. The contract for a stack:

```
cnoe-stacks/<language>-template/
├── stack.yaml              # name, version, vars, source/gitops template paths
├── app-source/             # files copied to <app>-source repo
│   ├── ...
└── ...

cnoe-stacks/<language>-gitops-template/
├── stack.yaml              # name, version, target namespace defaults
├── deployment.yaml
├── service.yaml
├── ingress.yaml
└── kustomization.yaml      # to be added; normalises with templates/ richer variant
```

A `stack.yaml` is the index that future agent versions will read to discover templates, validate variables, and pick a stack based on language detection. Until that lands, the agent uses hard-coded paths in `populate_repo_from_stack()` (`agent.py:191`).

Vendoring the stacks (rather than pulling at runtime) gives us reproducible demos and lets us pin the template version in Git.

## Consequences

### Positive

- Single, version-controlled location for all stacks.
- Canonical structure makes it easy to add a Python or Go stack.
- `stack.yaml` provides the metadata needed for future multi-stack selection.

### Negative / Costs

- Templates evolve in lock-step with the agent; pinning happens via Git, not via a registry.
- The `templates/` directory needs a cleanup pass.
- We diverge slightly from `cnoe-io/stacks` if upstream doesn't adopt `stack.yaml`.

### Neutral

- The agent's `populate_repo_from_stack()` continues to work unchanged in the short term.

## Compliance & Security Considerations

- Vendored templates are subject to the same code review as application source. New stacks must be reviewed for image base layers, default RBAC, and secret references before being merged.
- The agent must not load templates from outside `cnoe-stacks/`; this prevents a malicious request from pointing to a path traversal target.

## Follow-up Work

- [ ] Move `templates/nodejs-app-template/{configmap.yaml,kustomization.yaml,README.md}` enhancements into `cnoe-stacks/nodejs-template/` and `cnoe-stacks/nodejs-gitops-template/`.
- [ ] Delete `templates/` after migration is verified by tests.
- [ ] Define and enforce `stack.yaml` schema.
- [ ] Add a Python stack (`python-template/`) once the schema is stable.

## References

- ADR-0006 — Two-repository pattern (templates feed both).
- ADR-0007 — Jinja2 template rendering.
- Upstream: <https://github.com/cnoe-io/stacks>.
- DDD: *Stack* and *Stack Template* aggregates.
