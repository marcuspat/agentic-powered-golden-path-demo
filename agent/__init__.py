"""Golden Path AI-powered onboarding agent.

This package implements the Domain-Driven Design model documented under
``docs/ddd/`` and the architectural decisions captured in ``docs/adr/``.

The package is organised in four layers:

- ``agent.domain``           — value objects, aggregates, domain services, ports.
- ``agent.application``      — application services that drive the domain.
- ``agent.infrastructure``   — adapters that implement domain ports against
                               external systems (GitHub, OpenRouter, kubectl, …).
- ``agent.cli`` / ``agent.composition`` — the entry point and the wiring root.

The legacy entry point ``ai-onboarding-agent/agent.py`` is preserved as a thin
shim that re-exports :func:`agent.cli.main`.
"""

__version__ = "0.2.0"
