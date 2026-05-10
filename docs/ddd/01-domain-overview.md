# 01 — Domain Overview

## Purpose of the platform

The Golden Path platform turns a developer's natural-language intent — *"Create a NodeJS service called `inventory-api`"* — into a deployed, observable application running on Kubernetes, with source code, deployment configuration, and an operational footprint already in place. The goal is to compress the *first hour* of a new service from days of bespoke setup to minutes of automated, opinionated work.

## The core domain

The **core domain** is **Service Onboarding** — the set of business rules and workflows that take a request for a new service and produce a running, observable, GitOps-managed application. The platform's competitive value (in business terms) is in *how good its golden paths are* and *how reliably the agent walks them*. Everything else is supporting or generic.

## Subdomains

Following Eric Evans's classification, we identify three categories of subdomain:

### Core subdomain

| Subdomain                | What it owns                                                                              |
|--------------------------|-------------------------------------------------------------------------------------------|
| **Service Onboarding**   | Translating intent into a fully-provisioned application; the orchestration of all tools. |

### Supporting subdomains

These embody knowledge that is essential but not differentiating; they encode our opinions but use mostly off-the-shelf components.

| Subdomain                       | What it owns                                                                              |
|---------------------------------|-------------------------------------------------------------------------------------------|
| **Stack Catalog**               | Definition of golden-path stacks (NodeJS, future: Python/Go), templates, and parameters. |
| **Source Code Provisioning**    | Creation and population of `*-source` repositories.                                       |
| **GitOps Configuration**        | Creation and population of `*-gitops` repositories with deployment manifests.            |
| **Deployment Orchestration**    | Translation of GitOps state into ArgoCD `Application` resources and cluster reality.      |
| **Observability**               | Auto-wiring metrics/logs/traces into every onboarded application.                         |

### Generic subdomains

These are commoditised; we adopt off-the-shelf solutions and don't model them deeply.

| Subdomain               | What it owns                                                            |
|-------------------------|-------------------------------------------------------------------------|
| **Identity & Access**   | GitHub authentication, ArgoCD RBAC.                                     |
| **Version Control**     | Git protocol, commits, branches, history.                               |
| **Container Runtime**   | Kubernetes, KinD, Docker.                                               |
| **DNS & Ingress**       | localtest.me, nginx.                                                     |
| **LLM Inference**       | OpenRouter and downstream model providers.                               |

## Actors

| Actor                       | Type     | Description                                                                            |
|-----------------------------|----------|----------------------------------------------------------------------------------------|
| **Developer**               | Human    | Issues a natural-language onboarding request and consumes the resulting application.   |
| **Platform Engineer**       | Human    | Authors stacks, owns the GitOps templates, operates the cluster.                       |
| **Onboarding Agent**        | Software | The Python CLI that orchestrates the flow.                                             |
| **LLM Provider**            | External | OpenRouter and the chosen model (e.g. GPT-3.5).                                        |
| **GitHub**                  | External | Repository hosting and Git protocol.                                                   |
| **ArgoCD**                  | External | GitOps reconciler.                                                                     |
| **Tekton**                  | External | In-cluster CI (post-onboarding).                                                       |
| **Kubernetes API**          | External | Cluster control plane.                                                                 |

## Domain narrative

A Developer says, in plain English, what kind of service they want. The Onboarding Agent extracts the **App Name** (a value object with strict rules — lowercase, hyphens-only, DNS-compatible), selects a **Stack** from the catalog, and walks the **Onboarding Workflow**:

1. **Source Code Provisioning** creates `<app>-source` and renders the language template into it.
2. **GitOps Configuration** creates `<app>-gitops` and renders the deployment template, parameterised by the **App Name** and **Namespace**.
3. **Deployment Orchestration** materialises an **Argo Application** that points at `<app>-gitops`.
4. **Deployment Orchestration** then steps back; ArgoCD reconciles the desired state into a running **Workload** in the App's **Namespace**.
5. **Observability** auto-wires telemetry (via the GitOps template) so the new Workload appears in dashboards immediately.

Each step emits a **Domain Event** (`SourceRepositoryCreated`, `GitOpsRepositoryPopulated`, `ArgoApplicationRegistered`, `WorkloadHealthy`). Today these events are log lines; the model treats them as first-class citizens that future automations (Slack notifications, audit pipelines, billing) can subscribe to.

## Where to look for what

| You want to know …                                  | Read …                                                        |
|------------------------------------------------------|---------------------------------------------------------------|
| What a term means                                    | [`02-ubiquitous-language.md`](./02-ubiquitous-language.md)    |
| How the system divides into modules                  | [`03-bounded-contexts.md`](./03-bounded-contexts.md)          |
| How modules relate to each other                     | [`04-context-map.md`](./04-context-map.md)                    |
| How to model a single use case in code               | [`05-aggregates-and-entities.md`](./05-aggregates-and-entities.md), [`08-domain-services.md`](./08-domain-services.md) |
| What facts the system emits                          | [`07-domain-events.md`](./07-domain-events.md)                |
| How to wire it all into the existing CLI             | [`12-implementation-guide.md`](./12-implementation-guide.md)  |
