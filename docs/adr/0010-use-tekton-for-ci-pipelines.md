# ADR-0010: Use Tekton for in-cluster CI pipelines

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** ci, tekton, kubernetes, build

## Context

The agent today provisions a deployment that pulls a *pre-built public image* (`gcr.io/google-samples/hello-app:1.0` in the example manifest). For the full Golden Path — build, test, sign, push, deploy — we need a continuous-integration system that:

- Runs inside the same Kubernetes cluster the agent provisions, to keep the demo self-contained.
- Exposes a CRD-based pipeline definition that lives in the GitOps repository alongside the deployment manifests.
- Integrates with ArgoCD so that a Tekton-built image bump becomes a Git commit on `*-gitops`, triggering an ArgoCD sync.

idpbuilder installs Tekton Pipelines and Triggers as part of its default stack (ADR-0002).

## Decision Drivers

- Already installed by idpbuilder; zero additional moving parts.
- Kubernetes-native; pipelines are CRDs and `Run` resources are observable like any other workload.
- GitHub webhook compatibility through Tekton Triggers.
- Composes with `argocd-image-updater` for the image-bump flow.

## Considered Options

1. **Tekton Pipelines** in-cluster.
2. **GitHub Actions** with a self-hosted runner.
3. **Argo Workflows** (also in-cluster, but heavier).
4. **Jenkins** (requires its own server, far heavier).

## Decision

We will adopt **Tekton Pipelines and Triggers** as the canonical CI engine. The pipeline contract is:

1. A `PipelineRun` is triggered by a `push` webhook to `*-source`.
2. Stages: `clone → unit-test → build → push → bump-gitops`.
3. The final stage commits an image tag bump to `*-gitops/deployment.yaml`.
4. ArgoCD picks up the GitOps commit and syncs the new image into the cluster.

The pipeline definition itself ships in a *new* directory `cnoe-stacks/nodejs-template/.tekton/` (to be created) and is rendered into `*-source` along with the application code.

> **Implementation status (as of this ADR):** the agent currently does not seed `.tekton/` content because the demo uses a pre-built image. This ADR captures the intended design; the work item is tracked under *Follow-up*.

## Consequences

### Positive

- Self-contained, in-cluster CI — no extra infrastructure.
- Pipelines are version-controlled CRDs; they go through the same review process as any manifest.
- ArgoCD sees pipeline state as cluster state; one pane of glass.

### Negative / Costs

- Tekton has a learning curve for developers familiar only with YAML CI files (e.g. GitHub Actions).
- Image registry credentials must be configured per cluster (sealed/external secrets — ADR-0018).
- Cold-start of Pipeline pods is slower than warm runner-based systems.

### Neutral

- The agent does not need to know about Tekton at all; the pipeline lives in template files. The agent's role ends at "GitOps repo created and ArgoCD application registered".

## Compliance & Security Considerations

- Tekton runs as a privileged controller; ensure RBAC limits `PipelineRun` creation to specific namespaces.
- Image push credentials must be stored as Kubernetes secrets, ideally via External Secrets Operator (ADR-0018).
- Use `cosign`/`sigstore` for image signing as a follow-up; the GitOps deployment can then verify signatures with a policy controller.

## Follow-up Work

- [ ] Add `cnoe-stacks/nodejs-template/.tekton/{pipeline.yaml,task-build.yaml,task-test.yaml,trigger.yaml}`.
- [ ] Document the per-cluster image registry secret bootstrap.
- [ ] Add a Tekton-based smoke test in `tests/` once pipelines exist.

## References

- ADR-0002 — idpbuilder installs Tekton.
- ADR-0003 — ArgoCD picks up GitOps commits made by the pipeline.
- ADR-0018 — Secret management for registry credentials.
- Tekton docs: <https://tekton.dev/>.
