# ADR-0008: Use GitHub as the version control provider

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering, Agent Engineering
- **Tags:** vcs, github, integration

## Context

The agent creates two repositories per onboarded application (ADR-0006), pushes initial commits to them, and ArgoCD subsequently pulls from the GitOps repository. We need a hosted Git provider with:

- A stable REST API for repository creation.
- HTTPS-based authentication that works over a personal access token (PAT).
- Familiarity for the audience — most demo viewers and contributors already have a GitHub account.
- A free tier sufficient to host the two demo repositories per app.

Alternatives include the Gitea instance bundled with idpbuilder, GitLab, and Bitbucket.

## Decision Drivers

- Lowest friction for the demo audience; everyone has a GitHub account.
- Mature `PyGithub` SDK for repository creation.
- ArgoCD has first-class support for GitHub including webhook delivery.
- Webhook surface and Marketplace integrations for follow-up work.

## Considered Options

1. **GitHub** (cloud).
2. **Gitea** local instance bundled with idpbuilder.
3. **GitLab** (cloud or self-hosted).
4. **Mixed: GitHub for source, Gitea for GitOps** to keep deployments fully local.

## Decision

We will use **GitHub** as the canonical VCS provider for both `*-source` and `*-gitops` repositories. The agent authenticates with a PAT supplied via `GITHUB_TOKEN` (ADR-0014) and reads the user/organization from `GITHUB_USERNAME`. Repositories are created public by default to make the demo easy to inspect.

If a repository already exists, the agent logs a warning and falls back to the deterministic URL `https://github.com/<user>/<app>-{source,gitops}.git`, allowing re-runs of the demo on the same name.

## Consequences

### Positive

- Lowest barrier to entry for the demo audience.
- Mature SDKs and webhooks.
- ArgoCD integrates cleanly via HTTPS with PAT.

### Negative / Costs

- A personal GitHub account is a hard prerequisite; offline demos require the alternative path through bundled Gitea (a future ADR if needed).
- Public repositories leak the demo's app names; an org-level demo should switch to private repositories.
- API rate limits (5000 req/hour for an authenticated user) bound the throughput of repeated demos.

### Neutral

- Provider is encapsulated in `create_github_repo()`; switching to GitLab or Gitea would be a single function refactor and an ADR.

## Compliance & Security Considerations

- The PAT must have `repo` scope for repository creation. Use a fine-grained token scoped to the demo user where possible.
- The PAT is read from `GITHUB_TOKEN`; never log it. The agent's logger does not echo environment variables.
- Public repository creation is the default. For company demos, set a `GITHUB_PRIVATE=true` flag in a future change so manifests don't leak into search engines.
- Push URLs use HTTPS; ensure the local Git config does not store the PAT in plaintext under `~/.git-credentials` for shared workstations.

## Follow-up Work

- [ ] Add `GITHUB_PRIVATE` toggle that sets `private=True` in `create_repo()`.
- [ ] Document the offline path through Gitea (idpbuilder bundle) as an alternative profile.
- [ ] Add CODEOWNERS templates to both repositories upon creation.

## References

- ADR-0006 — Two-repository pattern.
- ADR-0014 — Environment-variable configuration.
- ADR-0018 — Secret management (handling the PAT).
- `PyGithub` docs: <https://pygithub.readthedocs.io/>.
