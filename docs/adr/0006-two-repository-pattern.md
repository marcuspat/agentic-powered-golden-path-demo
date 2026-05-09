# ADR-0006: Adopt the two-repository pattern (source + GitOps)

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering, Agent Engineering
- **Tags:** gitops, repository-strategy, separation-of-concerns

## Context

Each onboarded application has two distinct sets of artefacts:

1. **Application source code** — `index.js`, `package.json`, `Dockerfile`, language-specific tests, developer-owned.
2. **Deployment configuration** — Kubernetes manifests, ArgoCD `Application`, ingress, kustomization, platform-owned.

These artefacts have different audiences, different review processes, and different change frequencies. Application code changes daily; deployment configuration changes when SLOs, replica counts, or platform versions move. They often have different access controls — a developer should be able to merge code freely but should not unilaterally bump production replica counts.

`agent.py` already produces two repositories: `<app>-source` and `<app>-gitops` (`create_github_repo`, `agent.py:15`). This ADR records the decision and the contract.

## Decision Drivers

- Independent change cadence and reviewers for code vs. config.
- ArgoCD watches a *config* repository, not a source repository — mixing both forces ArgoCD to ignore most of what it sees and complicates path filters.
- Developer commits should not have to wait for a deployment review.
- Simpler RBAC; the GitOps repository can be locked down separately.

## Considered Options

1. **Two repositories** (`<app>-source`, `<app>-gitops`).
2. **Monorepo per application** with `app/` and `gitops/` subdirectories.
3. **One central GitOps repository** for all applications, plus per-app source repos.
4. **One central monorepo** for everything.

## Decision

We adopt **two repositories per onboarded application**:

- `<app>-source` — application code, populated from `cnoe-stacks/nodejs-template/app-source/`.
- `<app>-gitops` — deployment manifests, populated from `cnoe-stacks/nodejs-gitops-template/`. ArgoCD's `Application` CR points at this repo with `path: .` and `targetRevision: HEAD`.

Both repositories are created in the developer's GitHub user/organization namespace by the agent in a single transaction. If either creation fails, the agent surfaces the error and the demo aborts with a non-zero exit code.

Option 3 is a viable evolution: as the platform scales beyond a single team, a central GitOps repository keyed by `apps/<app>/` may replace per-app GitOps repositories. That migration is out of scope for the demo and would be its own ADR.

## Consequences

### Positive

- Clean separation of *what runs* from *what is built*.
- ArgoCD's repository configuration is a single root path, no filtering needed.
- Per-repo branch protection and reviewers; platform owns `*-gitops`, the team owns `*-source`.
- Aligns with the **Source Code** and **GitOps** bounded contexts in the DDD model.

### Negative / Costs

- Twice as many repositories to track and back up.
- Image bumps require a commit to the GitOps repo (typically automated via Tekton + `argocd-image-updater`).
- Initial onboarding creates two GitHub repos, doubling the rate-limit budget per request.

### Neutral

- The agent's `populate_repo_from_stack()` function is called twice (once per repo) with different template paths.

## Compliance & Security Considerations

- **Branch protection** — the GitOps repository must require pull-request review for changes to environments labelled production.
- **Token scope** — the agent's GitHub token (ADR-0008) needs `repo` scope, which grants both create and write. Use a fine-grained token and scope it to the user's account.
- **Separation of duties** — give developers write access to `*-source` and read-only access to `*-gitops`; promotions go through PRs reviewed by platform.

## Follow-up Work

- [ ] Add a CODEOWNERS template to `*-gitops` so the platform team is auto-requested for review.
- [ ] Implement central GitOps repo migration plan (separate ADR) when the second team onboards.

## References

- ADR-0003 — ArgoCD watches `*-gitops` only.
- ADR-0008 — GitHub as VCS provider.
- ADR-0012 — `cnoe-stacks` templates feed both repos.
- DDD: *Source Code Repository* and *GitOps Repository* aggregates.
