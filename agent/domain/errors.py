"""Domain exception hierarchy.

Adapters translate foreign exceptions (PyGithub, openai, kubernetes,
subprocess) into these domain exceptions before they cross the
infrastructure → domain boundary. Domain code never raises
``requests.HTTPError``, ``kubernetes.client.exceptions.ApiException``, etc.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional


class DomainError(Exception):
    """Base class for every domain-layer exception."""


# ---------------- LLM ---------------- #

class LlmUnavailable(DomainError):
    """Raised when the LLM cannot fulfil a request.

    Always non-fatal: ``IntentExtractionService`` catches it and falls through
    to the regex path (ADR-0011).
    """


# ---------------- VCS / GitHub ---------------- #

class Unauthorized(DomainError):
    """Authentication/authorization failure against an external system."""


class RateLimited(DomainError):
    """The remote service rate-limited us."""

    def __init__(self, message: str, retry_after: Optional[timedelta] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class RepositoryAlreadyExists(DomainError):
    """A repository with the requested name already exists. Often non-fatal."""


class RepositoryQuotaExceeded(DomainError):
    """The user/org GitHub repo quota is exhausted."""


class GitOutOfDate(DomainError):
    """Push rejected because the local copy is behind."""


# ---------------- Kubernetes ---------------- #

class K8sApplyError(DomainError):
    """``kubectl apply`` (or the python SDK) reported an error."""


# ---------------- Stack catalog ---------------- #

class StackNotFound(DomainError):
    """Requested stack name does not exist in the catalog."""


class TemplateRenderError(DomainError):
    """Template rendering failed (missing var, syntax error, undeclared var)."""


# ---------------- Generic ---------------- #

class ExternalSystemError(DomainError):
    """Any uncategorised failure from an external system."""

    def __init__(self, system: str, original: BaseException) -> None:
        super().__init__(f"{system}: {original}")
        self.system = system
        self.original = original
