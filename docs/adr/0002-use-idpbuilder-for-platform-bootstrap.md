# ADR-0002: Use idpbuilder to bootstrap the local IDP

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** platform, kubernetes, bootstrap, cnoe

## Context

The demo must stand up a complete Internal Developer Platform (IDP) — a Kubernetes cluster, ArgoCD, Tekton, an ingress gateway, and supporting CRDs — on a developer's laptop in minutes, with Docker as the only prerequisite. Building this stack from raw `kind`, Helm, and `kubectl apply` invocations is possible but slow, brittle, and produces drift between contributors' environments.

`cnoe-io/idpbuilder` is a CNOE-curated single binary that provisions a KinD cluster preconfigured with ArgoCD, Tekton, an nginx ingress, Gitea (optional), and the localtest.me TLS certificates needed for friendly URLs. It is the canonical CNOE bootstrap tool and is referenced in `plan.md` as the foundation of the project.

## Decision Drivers

- Single-command, reproducible cluster bootstrap.
- Pre-wired ArgoCD, Tekton, and ingress so the agent can focus on the onboarding flow.
- Friendly, signed `*.cnoe.localtest.me` URLs out of the box.
- Aligned with the wider CNOE ecosystem the project is meant to demonstrate.
- Single binary; no Helm chart sprawl in this repository.

## Considered Options

1. **Use idpbuilder.** Single binary, installs the full CNOE stack.
2. **Hand-roll with `kind` + `helm`** scripts in `scripts/`.
3. **Use `minikube` or `k3d`** with our own add-on installers.
4. **Use a managed Kubernetes service** (EKS, GKE, AKS) per developer.

## Decision

We will use **idpbuilder** as the sole bootstrap mechanism for the demo platform. The repository ships the binary at `./idpbuilder` and the source under `idpbuilder-source/` so that contributors can rebuild or pin a specific commit.

The agent never speaks to the cluster bootstrap layer; it assumes a working ArgoCD endpoint and a kubeconfig. This keeps the agent decoupled from the bootstrap concern and aligns with the **Platform Provisioning** bounded context (see DDD docs).

## Consequences

### Positive

- 15-to-20-minute first-run, then sub-minute restarts — meets the demo budget.
- Identical clusters across all contributors and CI runners.
- Aligns with CNOE; our work composes with other CNOE tooling.
- The bootstrap concern is encapsulated in one binary that we can pin.

### Negative / Costs

- Lock-in to idpbuilder's opinions about ingress controllers, certificates, and namespacing.
- The binary is large (~50 MB) and is committed to the repository, which inflates clone size.
- Upstream changes to idpbuilder can force template or ADR updates here.

### Neutral

- Developers wanting an alternative cluster (k3d, real cloud) must replicate the ArgoCD + Tekton + ingress stack themselves before the agent will succeed.

## Compliance & Security Considerations

idpbuilder generates a self-signed CA for `*.cnoe.localtest.me`. This is acceptable for local development but **must not** be used outside a developer laptop. Production deployments are out of scope for this repository.

## Follow-up Work

- [ ] Add a `make bootstrap` target that wraps `./idpbuilder create` and prints the ArgoCD password.
- [ ] Document the upgrade path when a new idpbuilder release lands.

## References

- ADR-0009 — Use KinD as the local Kubernetes runtime (chosen by idpbuilder).
- ADR-0010 — Use Tekton for in-cluster CI pipelines (installed by idpbuilder).
- ADR-0016 — Use localtest.me for local DNS resolution (provided by idpbuilder).
- Upstream: <https://github.com/cnoe-io/idpbuilder>.
