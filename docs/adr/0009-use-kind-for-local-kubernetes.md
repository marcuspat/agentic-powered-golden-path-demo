# ADR-0009: Use KinD as the local Kubernetes runtime

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering
- **Tags:** kubernetes, local-dev, kind

## Context

The demo must run a real Kubernetes cluster on a developer's laptop with Docker as the only prerequisite (ADR-0002). idpbuilder selects KinD ("Kubernetes in Docker") as its runtime: each Kubernetes node runs as a Docker container, the cluster comes up in under a minute on warm caches, and the API server speaks the same gRPC contract as a managed cluster.

This decision is largely consequential to ADR-0002 (idpbuilder), but it has standalone implications worth recording: KinD-specific networking, image loading, port-forwarding, and storage behaviours affect both the agent and the templates.

## Decision Drivers

- Single Docker dependency; no second VM (Minikube), no extra runtime (k3d uses k3s).
- Multi-node support if needed for HA demos.
- Conformance with upstream Kubernetes (CNCF certified).
- Mature support in CI runners (GitHub Actions has KinD actions).

## Considered Options

1. **KinD** (Kubernetes in Docker) — idpbuilder default.
2. **k3d** (k3s in Docker) — lighter, uses sqlite by default, less CNCF-aligned.
3. **Minikube** — supports multiple drivers but requires either Docker, a VM driver, or a hypervisor.
4. **Cloud-managed (EKS/GKE/AKS)** per developer.
5. **Local Docker Desktop Kubernetes** — limited multi-node, version lag.

## Decision

We will use **KinD** as the Kubernetes runtime for the demo, as selected by idpbuilder. The cluster name is `demo-cluster` by default. A single control-plane node is sufficient for the demo; templates assume one node and one ingress controller (`nginx` provided by idpbuilder).

For loading locally-built container images into KinD — for instance after a Tekton build — use `kind load docker-image` (wrapped by `idpbuilder`). The agent itself does not build images; it relies on Tekton or pre-built public images.

## Consequences

### Positive

- Closest fit to upstream Kubernetes; conformance gives us confidence the demo stack would work on EKS/GKE.
- Fast cold-start (~30-60 s once Docker image cache is warm).
- Multi-node configs are possible for advanced demos.
- Aligned with idpbuilder defaults; no custom KinD config needed for the happy path.

### Negative / Costs

- Memory hungry; each KinD node holds a full kubelet, control-plane, and CNI in a Docker container.
- KinD's default storage driver requires `hostPath` and is not durable across cluster recreations.
- Cross-platform networking quirks (Linux vs. macOS) must be handled by ingress configuration; idpbuilder hides most of this.

### Neutral

- The agent only sees `~/.kube/config`; if a user replaces KinD with EKS, the same agent code runs unchanged provided ArgoCD and ingress are present.

## Compliance & Security Considerations

- KinD nodes share a Docker bridge network with the host. Ensure firewalls block external access if you run the demo on a workstation with public network exposure.
- Cluster credentials in `~/.kube/config` are long-lived. Rotate by destroying and recreating the cluster (`./idpbuilder delete && ./idpbuilder create`).

## Follow-up Work

- [ ] Document the multi-node demo configuration in `docs/`.
- [ ] Add `kind load docker-image` step to the Tekton pipeline once it lands.

## References

- ADR-0002 — idpbuilder bootstrap (selects KinD).
- ADR-0010 — Tekton pipelines run inside KinD.
- KinD docs: <https://kind.sigs.k8s.io/>.
