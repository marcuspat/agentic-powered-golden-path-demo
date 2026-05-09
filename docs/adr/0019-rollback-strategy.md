# ADR-0019: Roll back via Git revert plus ArgoCD re-sync

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering, SRE
- **Tags:** rollback, gitops, operations

## Context

When a deployment misbehaves we need a fast, well-understood, auditable way to restore the previous good state. The platform has two assets that determine the correct rollback shape:

- **GitOps repository** (`*-gitops`) — the desired state of the cluster, history visible.
- **ArgoCD** — the reconciler with `automated.selfHeal` and `prune` enabled (ADR-0003).

We must decide whether rollbacks are imperative (`kubectl rollout undo`, `argocd app rollback`) or declarative (Git history). Imperative rollbacks are fast but invisible to Git, leaving the repository's HEAD as the (now broken) "desired" state — ArgoCD will dutifully re-apply it and undo the rollback.

## Decision Drivers

- The rollback must survive the next ArgoCD sync.
- It must be auditable; "who rolled back what when" is answerable from Git.
- It must be the **same shape** as forward changes (a commit), so reviewers and tooling don't have a special case.
- Speed matters for incident response; we want a single command path.

## Considered Options

1. **`git revert` on the GitOps repo, then ArgoCD syncs.** Declarative, durable, auditable.
2. **`argocd app rollback <app> <revision>`.** Imperative; sets the App's `targetRevision`. Reverts when the next Git push lands.
3. **`kubectl rollout undo deployment/<app>`.** Imperative at the cluster level; ArgoCD will overwrite it.
4. **Branch-per-environment with merge train.** Heavyweight; better suited for multi-environment promotion.

## Decision

We will **roll back via `git revert` on the GitOps repository**, followed by an automatic ArgoCD sync. Concretely:

1. Identify the bad commit on `<app>-gitops`.
2. `git revert <bad-sha>` and push.
3. ArgoCD detects the new HEAD within its poll interval (or immediately via webhook) and applies the previous manifests.
4. Deployment health returns within the application's readiness window.

A `scripts/rollback.sh` wrapper exists to standardise the path and is documented as the canonical rollback procedure. Imperative options (`argocd app rollback`, `kubectl rollout undo`) remain available for break-glass scenarios but **must** be followed by a `git revert` to restore Git as the source of truth.

For the rare case where Git is the wrong source of truth (e.g. corrupted manifest), use `argocd app sync --revision <sha>` to pin to a known-good commit, then PR the fix.

## Consequences

### Positive

- Rollback is a Git operation; the same review and audit tools that govern forward changes govern rollbacks.
- Self-healing ArgoCD will *not* fight a Git-based rollback.
- A revert is its own forward commit — no rewriting history, no force-push.
- `scripts/rollback.sh` standardises the procedure for incident responders.

### Negative / Costs

- Slower than a `kubectl rollout undo` by the ArgoCD poll interval (mitigated by webhook).
- Requires the GitOps repo to be reachable; in a network partition, revert isn't possible.
- Cumulative reverts can become noisy in Git history; squash-merge for related fixes.

### Neutral

- The agent itself plays no part in rollback; it is involved only in initial onboarding.

## Compliance & Security Considerations

- All rollbacks appear in Git history with the responder as the author. Branch protection on `main` of `*-gitops` ensures a PR review for non-emergency reverts; for emergencies, configure a designated "incident" team that can bypass review with audit logging.
- The break-glass `kubectl`/`argocd` paths must be RBAC-restricted to on-call engineers; document the policy in a future operations ADR.

## Follow-up Work

- [ ] Add a webhook from GitHub `*-gitops` to ArgoCD to remove the polling delay.
- [ ] Add `scripts/rollback.sh --emergency` flag that does the imperative path *and* opens a follow-up PR.
- [ ] Add a chaos test in the failure-modes suite that asserts `git revert` restores health.

## References

- ADR-0003 — ArgoCD configuration with `selfHeal` and `prune`.
- ADR-0006 — Two-repository pattern (GitOps repo is the rollback surface).
- `scripts/rollback.sh` — the wrapper script.
