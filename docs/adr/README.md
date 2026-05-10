# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the **Golden Path AI-Powered Developer Onboarding** project.

An ADR captures a single, significant architectural decision: the context that prompted it, the alternatives considered, the choice made, and the resulting consequences. Together, the ADRs form the durable record of *why* the system looks the way it does — independent of the code, which only shows *what* was built.

## How to read this log

Read records in numerical order to follow the evolution of the architecture. Each record is self-contained and stamped with a status:

- **Proposed** — under discussion; not yet approved.
- **Accepted** — adopted; in force.
- **Deprecated** — no longer recommended but still in the codebase.
- **Superseded by ADR-NNNN** — replaced by a newer decision; included for history.

Decisions that are no longer accurate must not be edited; instead, add a new ADR that supersedes them.

## How to add a new ADR

1. Copy [`template.md`](./template.md) to `NNNN-short-title.md`, where `NNNN` is the next unused four-digit number.
2. Fill in the sections, keeping the title short and the prose tight.
3. Open a pull request. The decision is **Proposed** until merged; on merge, change the status to **Accepted**.
4. If the new record replaces an existing one, set the old record's status to *Superseded by ADR-NNNN* and link both ways.

## Index

| #    | Title                                                                                                  | Status   |
|------|--------------------------------------------------------------------------------------------------------|----------|
| 0001 | [Record architecture decisions](./0001-record-architecture-decisions.md)                               | Accepted |
| 0002 | [Use idpbuilder to bootstrap the local IDP](./0002-use-idpbuilder-for-platform-bootstrap.md)            | Accepted |
| 0003 | [Adopt ArgoCD for GitOps-based continuous delivery](./0003-adopt-argocd-for-gitops-deployment.md)      | Accepted |
| 0004 | [Use Python for the onboarding agent](./0004-use-python-for-onboarding-agent.md)                       | Accepted |
| 0005 | [Use OpenRouter as the LLM gateway](./0005-use-openrouter-as-llm-gateway.md)                           | Accepted |
| 0006 | [Adopt the two-repository pattern (source + GitOps)](./0006-two-repository-pattern.md)                 | Accepted |
| 0007 | [Use Jinja2 to render stack templates](./0007-use-jinja2-for-template-rendering.md)                    | Accepted |
| 0008 | [Use GitHub as the version control provider](./0008-use-github-as-vcs-provider.md)                     | Accepted |
| 0009 | [Use KinD as the local Kubernetes runtime](./0009-use-kind-for-local-kubernetes.md)                    | Accepted |
| 0010 | [Use Tekton for in-cluster CI pipelines](./0010-use-tekton-for-ci-pipelines.md)                        | Accepted |
| 0011 | [Provide a regex fallback for app-name extraction](./0011-pattern-matching-fallback.md)                | Accepted |
| 0012 | [Use cnoe-stacks templates as golden paths](./0012-use-cnoe-stacks-for-templates.md)                   | Accepted |
| 0013 | [Ship the agent as a single-process CLI](./0013-monolithic-cli-agent-architecture.md)                  | Accepted |
| 0014 | [Configure the agent through environment variables](./0014-environment-variable-configuration.md)      | Accepted |
| 0015 | [Adopt a layered, multi-tier testing strategy](./0015-multi-layer-testing-strategy.md)                 | Accepted |
| 0016 | [Use localtest.me for local DNS resolution](./0016-localtest-me-for-local-dns.md)                      | Accepted |
| 0017 | [Deploy onboarded apps to dedicated namespaces](./0017-namespace-isolation-strategy.md)                | Accepted |
| 0018 | [Manage credentials via cluster-native sealed/external credential stores](./0018-credential-management-approach.md) | Accepted |
| 0019 | [Roll back via Git revert plus ArgoCD re-sync](./0019-rollback-strategy.md)                            | Accepted |
| 0020 | [Observe with Prometheus, Grafana, and OpenTelemetry](./0020-observability-strategy.md)                | Accepted |

## Conventions

- Filenames use kebab-case and start with the four-digit number.
- One decision per record. If you find yourself describing multiple decisions, split the record.
- Prefer short prose over diagrams; reach for a diagram only when it removes ambiguity.
- Cross-reference related ADRs by number and short title.
- Reference the DDD documentation under [`../ddd/`](../ddd/) for the domain model that frames many of these decisions.
