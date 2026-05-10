# Domain-Driven Design Documentation

This directory contains the **Domain-Driven Design (DDD)** model for the *Golden Path AI-Powered Developer Onboarding* platform. It complements the [Architecture Decision Records](../adr/) (which capture *why*) and the source code (which captures *what*) by describing the **domain language and structure** the system implements.

## Why DDD here?

The platform's core problem isn't merely "wire up some APIs". It is to model the *act of bringing a new service into existence* — a workflow that crosses developer intent, source-code provenance, deployment configuration, cluster topology, and operational visibility. Each of those is its own subdomain with its own vocabulary; conflating them produces ambiguous code (`app`? application? Application CR? GitHub repo? deployment?). DDD gives us:

- A **ubiquitous language** so engineers, agents, and prompts use the same terms.
- **Bounded contexts** so each subdomain has a clean internal model and explicit translation at the boundary.
- **Aggregates and events** so we know what is consistent together and what propagates as a fact.

## How to read this set

Read in numerical order on first pass. After that, the documents are reference material:

| #     | Document                                             | Audience                                 |
|-------|------------------------------------------------------|------------------------------------------|
| 01    | [Domain Overview](./01-domain-overview.md)           | Everyone — the strategic shape           |
| 02    | [Ubiquitous Language](./02-ubiquitous-language.md)   | Everyone — the glossary                  |
| 03    | [Bounded Contexts](./03-bounded-contexts.md)         | Architects, agent engineers              |
| 04    | [Context Map](./04-context-map.md)                   | Architects, integrators                  |
| 05    | [Aggregates & Entities](./05-aggregates-and-entities.md) | Implementors                          |
| 06    | [Value Objects](./06-value-objects.md)               | Implementors                              |
| 07    | [Domain Events](./07-domain-events.md)               | Implementors, observability engineers    |
| 08    | [Domain Services](./08-domain-services.md)           | Implementors                              |
| 09    | [Repositories](./09-repositories.md)                 | Implementors                              |
| 10    | [Application Services](./10-application-services.md) | Implementors                              |
| 11    | [Anti-Corruption Layers](./11-anti-corruption-layers.md) | Integrators                          |
| 12    | [Implementation Guide](./12-implementation-guide.md) | Implementors, reviewers                  |

Diagrams live under [`./diagrams/`](./diagrams/) and are referenced from the documents above.

## Strategic vs. tactical

- **Strategic** (docs 01-04) is the high-altitude view: subdomains, contexts, integration patterns. Read these to understand the system's shape.
- **Tactical** (docs 05-09) is the implementation pattern catalogue: aggregates, value objects, events, services, repositories. Read these when writing code.
- **Application & integration** (docs 10-12) bridge the model to the executable system: orchestration, translation, and a step-by-step guide.

## Status of the model

The platform today is a working demo, not a production system. Several aggregates and events documented here are **not yet implemented in code**; they describe the *target* model that the codebase should evolve toward. Each document calls out implementation status explicitly. Where the gap is wide, the *Implementation Guide* (doc 12) lists the work items.

## Cross-references to ADRs

Every bounded context maps to one or more ADRs that explain the technology choices inside it. Look for the *Related ADRs* heading in each document.
