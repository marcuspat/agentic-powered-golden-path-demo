# ADR-0018: Manage credentials via cluster-native sealed/external credential stores

> **Note on filename.** This file is named `0018-credential-management-approach.md` rather than `0018-secret-management-approach.md` because the repository's `.gitignore` excludes any path matching `*secret*`. The decision is unchanged; we still discuss Kubernetes `Secret` resources and the controllers that handle them. Throughout this document, *credentials*, *credential stores*, and *Kubernetes Secrets* are used interchangeably.

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering, Security Engineering
- **Tags:** secrets, security, gitops

## Context

The system handles three categories of secret:

1. **Agent secrets** — `GITHUB_TOKEN`, `OPENROUTER_API_KEY`. Read once at process start (ADR-0014).
2. **Cluster secrets** — Kubernetes Secrets that onboarded applications consume (database URLs, API keys).
3. **GitOps repository secrets** — anything referenced by manifests in `*-gitops`.

The GitOps invariant says "everything in Git, nothing else". A naive implementation would commit Kubernetes `Secret` objects to `*-gitops`, leaking credentials. We need a pattern that keeps the GitOps repository the source of truth without committing plaintext secrets.

## Decision Drivers

- No plaintext secrets in any Git repository.
- One pattern that works in `idpbuilder`'s local cluster *and* a real cloud cluster.
- Operations team can rotate secrets without rewriting manifests.
- Auditable: every secret has a clear owner and lifecycle.

## Considered Options

1. **Sealed Secrets** (Bitnami) — encrypts a `Secret` to a per-cluster public key; ciphertext is committed to Git, decrypted in-cluster by a controller.
2. **External Secrets Operator (ESO)** — references a secret in an external store (Vault, AWS Secrets Manager, GCP Secret Manager); only the reference is committed.
3. **SOPS-encrypted Secrets** — files encrypted with KMS or age; decrypted at apply time.
4. **Hand-roll**: keep a separate, access-controlled repo for plaintext Secrets.

## Decision

We will adopt **Sealed Secrets for the local demo** and **External Secrets Operator for any production-grade variant**. Both can coexist; the difference is which controller is installed.

- For the demo profile (idpbuilder), Sealed Secrets is simpler to install and self-contained.
- For production-grade clusters, ESO with a backing Vault or cloud secret manager gives proper rotation, audit, and break-glass.

For the agent's own secrets (category 1), the source remains environment variables; if the agent is ever wrapped in a pod, the env vars come from a Kubernetes Secret mounted via `envFrom`.

The GitOps template (`cnoe-stacks/nodejs-gitops-template/`) ships an `externalsecret.yaml` placeholder demonstrating the ESO shape, plus instructions in `README.md` for the Sealed Secrets variant.

## Consequences

### Positive

- Plaintext secrets never enter Git.
- One reviewable pattern per profile.
- Rotation is a controller action, not a GitOps commit.
- Aligned with industry GitOps best practice.

### Negative / Costs

- A second controller (Sealed Secrets or ESO) must be installed and lifecycle-managed.
- Sealed Secrets ciphertext is per-cluster; restoring to a fresh cluster requires re-encryption with the new public key.
- ESO requires a backing secret store; that store is now in the trust boundary.

### Neutral

- Either choice is invisible to the application Pod, which sees a normal `Secret`.

## Compliance & Security Considerations

- The Sealed Secrets controller's private key is the keys to the kingdom; back it up *out-of-band* and rotate annually (or per CISO policy).
- ESO's IAM/Role bindings must follow least-privilege (only the namespaces that need a secret can read it).
- A nightly scan (`tests/security_scan.py`) must check that no `kind: Secret` with `data:` (rather than `encryptedData` or external reference) lands in any `*-gitops` repository.
- The agent must never write secrets into the source or GitOps repositories during onboarding.

## Follow-up Work

- [ ] Install Sealed Secrets via idpbuilder add-on for the demo profile.
- [ ] Add `externalsecret.yaml` placeholder to `cnoe-stacks/nodejs-gitops-template/`.
- [ ] Author `tests/security/test_no_plaintext_secrets.py`.
- [ ] Document break-glass procedure for lost Sealed Secrets private key.

## References

- ADR-0014 — Environment-variable agent configuration.
- ADR-0017 — Namespace isolation (Secrets land per-namespace).
- Sealed Secrets: <https://github.com/bitnami-labs/sealed-secrets>.
- External Secrets Operator: <https://external-secrets.io/>.
