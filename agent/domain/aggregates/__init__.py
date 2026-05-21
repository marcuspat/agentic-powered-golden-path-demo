"""Aggregates of the onboarding domain.

See ``docs/ddd/05-aggregates-and-entities.md``.
"""
from agent.domain.aggregates.argo_application import ArgoApplication
from agent.domain.aggregates.gitops_repository import GitOpsRepository
from agent.domain.aggregates.onboarding_run import OnboardingRun, OnboardingStep
from agent.domain.aggregates.source_repository import SourceRepository
from agent.domain.aggregates.stack import GitOpsTemplate, SourceTemplate, Stack

__all__ = [
    "ArgoApplication",
    "GitOpsRepository",
    "GitOpsTemplate",
    "OnboardingRun",
    "OnboardingStep",
    "SourceRepository",
    "SourceTemplate",
    "Stack",
]
