# {{ appName }} -- GitOps manifests

ArgoCD-watched deployment configuration for `{{ appName }}`. ArgoCD reconciles
this directory into namespace `{{ namespace | default(appName) }}` on the
cluster pointed to by the `Application` CR.

## Files

| File                  | Purpose                                                          |
|-----------------------|------------------------------------------------------------------|
| `namespace.yaml`      | Per-app namespace with Pod Security Standards `restricted`.      |
| `resourcequota.yaml`  | Modest CPU/memory/pod caps; bumps require a PR.                  |
| `networkpolicy.yaml`  | Default-deny ingress + DNS/observability egress allowlist.       |
| `configmap.yaml`      | Non-sensitive runtime configuration (`APP_NAME`, `NODE_ENV`).    |
| `externalsecret.yaml` | Placeholder ExternalSecret (swap to SealedSecret -- see below).  |
| `deployment.yaml`     | Workload, OTel env, probes on `/healthz` & `/readyz`, hardened.  |
| `service.yaml`        | ClusterIP on port 80 -> container port 8080, Prometheus annots.  |
| `ingress.yaml`        | nginx ingress at the configured host (default `<appName>.cnoe.localtest.me`) with wildcard TLS. |
| `servicemonitor.yaml` | Prometheus Operator scrape target for `/metrics`.                |
| `kustomization.yaml`  | Bundles the above for `kubectl apply -k .`.                      |
| `app.yaml`            | Canonical ArgoCD `Application` (applied to `argocd` namespace).  |

`app.yaml` is **not** included in `kustomization.yaml`: it lives one layer up
in ArgoCD's own namespace and points *at* this directory.

## Render

These files are Jinja2 templates; the agent renders them before pushing into
the `*-gitops` repository. Required variables:

- `appName` (required)
- `description` (required, used by `configmap.yaml`)
- `namespace` (optional, defaults to `appName`)
- `replicas` (optional, defaults to `2`)
- `image` (optional, defaults to `ghcr.io/cnoe-io/nodejs-hello:latest`)
- `host` (optional, defaults to `{{ appName }}.cnoe.localtest.me`)
- `gitopsRepoUrl` (required by `app.yaml`)

## Apply (after rendering)

```bash
# Workload (rendered manifests, namespace + everything else):
kubectl apply -k .

# ArgoCD application (rendered separately into the argocd namespace):
kubectl apply -f app.yaml
```

In normal operation you only apply `app.yaml` once; ArgoCD then keeps the rest
of the directory reconciled.

## Rollback

```bash
git revert <bad-commit>
git push
```

ArgoCD detects the new HEAD and re-syncs to the previous good state. With
`syncPolicy.automated.selfHeal=true`, no manual sync is required.

## Credential management

This template ships an `ExternalSecret` (see ADR-0018):

- **Production / cloud cluster** -- keep `externalsecret.yaml`. Configure a
  `ClusterSecretStore` named `cluster-secret-store` backed by Vault, AWS
  Secrets Manager, or GCP Secret Manager.
- **Local idpbuilder demo** -- replace `externalsecret.yaml` with a
  `SealedSecret` produced by `kubeseal` (the file header explains the swap).
  Update `kustomization.yaml`'s `resources:` accordingly.

Never commit a plaintext `kind: Secret` to this repository.
