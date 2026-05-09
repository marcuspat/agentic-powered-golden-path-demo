# ADR-0003: Adopt ArgoCD for GitOps-based continuous delivery

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** gitops, deployment, argocd, kubernetes

## Context

The agent must deploy onboarded applications to a Kubernetes cluster without holding long-lived cluster credentials beyond the bootstrap kubeconfig, and must give operators an auditable record of *what is running where and why*. The deployment mechanism must reconcile drift, surface health, and roll back cleanly via Git history.

The CNOE reference platform installed by `idpbuilder` (ADR-0002) ships ArgoCD as its GitOps controller. ArgoCD is the de facto standard pull-based reconciler for Kubernetes and integrates with the *GitOps* bounded context that this project is structured around.

## Decision Drivers

- **Pull model** — the cluster pulls desired state, so the agent does not need durable cluster credentials.
- **Auditability** — every change is a Git commit on the GitOps repository.
- **Drift detection** — ArgoCD detects and (optionally) self-heals divergence.
- **Multi-tenant view** — a single dashboard for many onboarded applications.
- **Already installed** by idpbuilder.

## Considered Options

1. **ArgoCD** — installed by idpbuilder, mature, large community.
2. **Flux v2** — also pull-based and CNCF-graduated, but not the idpbuilder default.
3. **Push-based `kubectl apply` from the agent** — simple, but the agent becomes the system of record and loses drift detection.
4. **Helm + CI deploy step** — adds infrastructure (CI runner) and weakens auditability.

## Decision

We will use **ArgoCD** as the sole continuous-delivery mechanism. The agent's third tool, `create_argocd_application()` (`ai-onboarding-agent/agent.py:91`), generates an `Application` CR pointing at the new app's GitOps repository and applies it via `kubectl`. ArgoCD takes over from there.

`syncPolicy.automated.prune` and `selfHeal` are both enabled so that deleted manifests are removed and out-of-band changes are reverted, matching the GitOps invariant *Git is the single source of truth*.

## Consequences

### Positive

- Cluster credentials live only in the bootstrap step; the agent does not push manifests directly to long-term workloads.
- Every onboarded application appears as a tile in ArgoCD with health, sync status, and history.
- Rollback is a `git revert` on the GitOps repository (see ADR-0019).
- Self-healing reduces manual operator load.

### Negative / Costs

- Sync latency: changes appear after ArgoCD's poll interval (default 3 min) unless a webhook is wired up.
- Operators must understand ArgoCD's sync semantics (auto vs. manual, prune, replace).
- Tight coupling between the *GitOps* and *Deployment Orchestration* contexts; replacing ArgoCD requires changes to both `create_argocd_application()` and the GitOps template `app.yaml`.

### Neutral

- The *Application* CR lives in the `argocd` namespace; workloads land in app-specific namespaces (ADR-0017).

## Compliance & Security Considerations

- The ArgoCD admin password is generated per cluster and surfaced via `kubectl -n argocd get secret argocd-initial-admin-secret`. Production deployments must replace this with SSO.
- ArgoCD's repository credentials are stored as Kubernetes secrets in the `argocd` namespace. For private GitOps repositories, configure repository credentials via sealed/external secrets (ADR-0018).
- Enable RBAC on the ArgoCD `Application` CRD so that only the agent's service account can create new applications in the production variant.

## Follow-up Work

- [ ] Wire a GitHub webhook into ArgoCD to remove the polling delay.
- [ ] Define an `AppProject` per team rather than using `default`.
- [ ] Add an `argocd-image-updater` integration for image bumps from Tekton.

## References

- ADR-0002 — idpbuilder installs ArgoCD.
- ADR-0006 — Two-repository pattern; ArgoCD watches the GitOps repo.
- ADR-0019 — Rollback strategy uses Git revert + ArgoCD re-sync.
- DDD: *Deployment Orchestration* bounded context; `ArgoApplication` aggregate.
- ArgoCD docs: <https://argo-cd.readthedocs.io/>.
