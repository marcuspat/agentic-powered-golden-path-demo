# ADR-0017: Deploy onboarded apps to dedicated namespaces

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** kubernetes, isolation, multi-tenancy, security

## Context

The current demo flow deploys every onboarded application into the `default` namespace (`agent.py:111`). This works for one application but causes:

- Resource collisions when two apps share a name.
- Diffuse RBAC; granting a developer permission to debug their app means granting access to everything else in `default`.
- No NetworkPolicy boundary between apps.
- A polluted "kubectl get all" view that's hard to demo.

We need a per-app isolation boundary and a clear naming convention.

## Decision Drivers

- Isolation between onboarded applications (RBAC, NetworkPolicy, ResourceQuota).
- Predictable naming so the agent and ArgoCD agree on where to deploy.
- Aligned with the idpbuilder reference platform conventions.
- Easy to grant a single developer access to "their" namespace only.

## Considered Options

1. **Namespace per app** — `<app-name>` as the namespace.
2. **Namespace per team** — `team-<team>` containing many apps.
3. **All apps in `default`** — current state.
4. **Namespace per environment per app** — `<app>-dev`, `<app>-staging`.

## Decision

We will deploy each onboarded application into a **dedicated namespace named after the application**. The agent's `create_argocd_application()` will set:

```yaml
spec:
  destination:
    server: https://kubernetes.default.svc
    namespace: {{ appName }}
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
```

Namespace creation is delegated to ArgoCD (`CreateNamespace=true`) so the agent never holds namespace-creation privileges directly. A baseline `NetworkPolicy` (deny-all-ingress, allow-egress-DNS+ingress-controller) and `ResourceQuota` are added to the GitOps template (`cnoe-stacks/nodejs-gitops-template/`) so every onboarded app inherits sane defaults.

For multi-environment deployments, ADR will be revisited; the immediate decision is *one namespace per application*. Environment splits land later as `<app>` plus an Argo `AppProject` per environment.

## Consequences

### Positive

- True isolation; an exhausted ResourceQuota in `inventory-api` cannot starve `payment-processor`.
- Clean per-app dashboards in ArgoCD, Prometheus, Grafana.
- RBAC can be granted per namespace.
- NetworkPolicy can be enforced per namespace.

### Negative / Costs

- More namespaces to clean up; `./idpbuilder delete` removes them but manual cleanup needs `kubectl delete ns <app>`.
- Cross-app communication requires explicit Service ↔ Service references with FQDN (`svc.<app-namespace>.svc.cluster.local`).
- Initial ResourceQuotas may be too small for some workloads; tune in the template.

### Neutral

- The change is encapsulated in `agent.py:create_argocd_application()` and the GitOps template's `kustomization.yaml` namespace setting.

## Compliance & Security Considerations

- Default-deny NetworkPolicy enforces a least-privilege baseline.
- ResourceQuotas mitigate one app exhausting the cluster.
- The ArgoCD service account that creates namespaces requires `namespaces: create`. Audit this permission and consider a dedicated `AppProject` per app to scope it further.
- Pod Security Standards (PSS) `restricted` should be applied to onboarded namespaces; add a label in the GitOps template (`pod-security.kubernetes.io/enforce: restricted`).

## Follow-up Work

- [ ] Update `cnoe-stacks/nodejs-gitops-template/` to include `namespace.yaml`, `networkpolicy.yaml`, `resourcequota.yaml`.
- [ ] Update `agent.py:create_argocd_application()` to set `destination.namespace` to `{{ appName }}` and `syncOptions: [CreateNamespace=true]`.
- [ ] Add the `pod-security.kubernetes.io/enforce: restricted` label to the namespace manifest.
- [ ] Document the cleanup command in the README troubleshooting section.

## References

- ADR-0003 — ArgoCD `Application` shape.
- ADR-0006 — Two-repository pattern (namespace lives in `*-gitops`).
- ADR-0018 — Secret management (per-namespace secrets).
- Kubernetes Pod Security Standards.
