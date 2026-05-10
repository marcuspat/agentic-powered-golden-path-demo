# Tekton CI for {{ appName }}

Per ADR-0010, this directory ships the canonical, in-cluster CI pipeline for
the source repository. It is rendered into the `*-source` repo so that the
pipeline lives next to the code it builds.

## Pipeline

`{{ appName }}-build` chains four tasks:

1. **fetch-source** -- `git-clone` (Tekton Catalog) checks out the commit.
2. **unit-test** -- `nodejs-unit-test` runs `npm ci && npm test`.
3. **build-and-push** -- `kaniko-build` produces an OCI image and pushes it.
4. **bump-gitops** -- `bump-gitops` clones the paired `*-gitops` repo,
   sed-replaces the `image:` line in `deployment.yaml`, commits with message
   `chore(gitops): bump {{ appName }} image to <ref>`, and pushes. ArgoCD
   reconciles from there.

## Params

| Param             | Required | Notes                                                        |
|-------------------|----------|--------------------------------------------------------------|
| `repo-url`        | yes      | HTTPS URL of the source repo (set by the trigger).           |
| `revision`        | yes      | Git SHA to build (set by the trigger from the push event).   |
| `image`           | yes      | Full image reference incl. tag (e.g. `ghcr.io/.../{{ appName }}:abc`). |
| `gitops-repo-url` | yes      | HTTPS URL of the paired GitOps repo to bump.                 |

## Install

```bash
kubectl apply -k .tekton/
```

This creates the `Pipeline`, three `Task`s, and the GitHub `EventListener` +
`TriggerBinding` + `TriggerTemplate`.

## Required secrets

The pipeline assumes three secrets exist in the namespace where it runs.
Create them via External Secrets Operator (preferred, ADR-0018) or
Sealed Secrets for the local idpbuilder demo.

| Secret name                          | Contents                                                  |
|--------------------------------------|-----------------------------------------------------------|
| `{{ appName }}-registry-credentials` | `config.json` with a registry login (mounted into kaniko).|
| `{{ appName }}-github-webhook`       | Key `secretToken` -- shared secret for webhook validation.|
| `{{ appName }}-gitops-push-token`    | A Git push credential for the bump-gitops step.           |

A `ServiceAccount` named `tekton-triggers-sa` with the standard Tekton
Triggers RBAC must also exist in the namespace.

## GitHub webhook

1. Expose the `EventListener` Service via an `Ingress` (or `kubectl
   port-forward`).
2. In your GitHub repo: **Settings -> Webhooks -> Add webhook**.
3. Payload URL: `https://<event-listener-host>/`.
4. Content type: `application/json`.
5. Secret: same value stored in `{{ appName }}-github-webhook.secretToken`.
6. Events: **Just the `push` event**.

## See also

- ADR-0010 -- Tekton choice and rationale.
- ADR-0006 -- Two-repo pattern (this pipeline writes across both).
- ADR-0018 -- Where the secrets above come from.
