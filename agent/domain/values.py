"""Value objects for the onboarding domain.

Value objects are immutable and equality-by-value. Each one encodes a domain
rule (validation, normalisation, formatting) so that primitive strings and ints
cannot stand in for richer concepts at the boundaries of the system.

See ``docs/ddd/06-value-objects.md`` for the catalogue and rationale.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import FrozenSet, Optional


# --------------------------------------------------------------------------- #
# Slug-like identifiers
# --------------------------------------------------------------------------- #

_DNS_LABEL_RE = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")
_DNS_LABEL_MAX = 63


@dataclass(frozen=True)
class AppName:
    """A DNS-compatible application slug.

    Lowercase ASCII, ``a-z``/``0-9``/``-``, must start and end with
    alphanumeric, max 63 chars (RFC 1123 DNS label).
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(f"AppName must be str, got {type(self.value).__name__}")
        if not _DNS_LABEL_RE.fullmatch(self.value):
            raise ValueError(f"Invalid AppName: {self.value!r}")

    @classmethod
    def from_raw(cls, raw: str) -> "AppName":
        """Normalise an arbitrary string into a valid AppName.

        This is the *only* sanctioned sanitiser; both the LLM extraction path
        and the regex fallback in ``IntentExtractionService`` route through it.

        Normalisation steps (in order):

        1. ``strip`` and lowercase
        2. Replace whitespace, ``_`` and ``.`` with ``-``
        3. Remove any remaining characters outside ``[a-z0-9-]``
        4. Collapse runs of ``-`` and trim leading/trailing ``-``
        5. Truncate to 63 chars (RFC 1123 DNS label limit)
        """
        if raw is None:
            raise ValueError("AppName.from_raw received None")
        s = raw.strip().lower()
        s = re.sub(r"[\s_.]+", "-", s)
        s = re.sub(r"[^a-z0-9-]", "", s)
        s = re.sub(r"-+", "-", s).strip("-")
        if not s:
            raise ValueError(f"Empty AppName after normalisation of {raw!r}")
        return cls(s[:_DNS_LABEL_MAX])

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Namespace:
    """A Kubernetes namespace name. Same syntactic constraints as AppName."""

    value: str

    def __post_init__(self) -> None:
        if not _DNS_LABEL_RE.fullmatch(self.value):
            raise ValueError(f"Invalid Namespace: {self.value!r}")

    @classmethod
    def from_app(cls, app_name: AppName) -> "Namespace":
        """Project the app-name namespace convention (ADR-0017)."""
        return cls(app_name.value)

    def __str__(self) -> str:
        return self.value


# --------------------------------------------------------------------------- #
# Onboarding request / outcome
# --------------------------------------------------------------------------- #

_REQUEST_MAX_BYTES = 4096


@dataclass(frozen=True)
class OnboardingRequest:
    """Wraps the raw user utterance."""

    text: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("OnboardingRequest.text must be non-empty")
        if len(self.text.encode("utf-8")) > _REQUEST_MAX_BYTES:
            raise ValueError(
                f"OnboardingRequest exceeds {_REQUEST_MAX_BYTES} bytes"
            )


@dataclass(frozen=True)
class AppDescription:
    """Free-text description of an onboarded application."""

    text: str

    def __post_init__(self) -> None:
        if self.text is None:
            raise ValueError("AppDescription.text must not be None")
        if len(self.text) > 512:
            raise ValueError("AppDescription too long (max 512 chars)")

    @classmethod
    def for_app(cls, app_name: AppName) -> "AppDescription":
        return cls(f"NodeJS application for {app_name.value}")


class OutcomeKind(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Outcome:
    """Terminal outcome of an OnboardingRun (or PipelineRun)."""

    kind: OutcomeKind
    reason: Optional[str] = None
    failed_step: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind is OutcomeKind.FAILED:
            if not self.reason:
                raise ValueError("Failed Outcome requires a reason")
            if not self.failed_step:
                raise ValueError("Failed Outcome requires a failed_step")
        if self.kind is OutcomeKind.SUCCEEDED:
            if self.reason or self.failed_step:
                raise ValueError("Succeeded Outcome must not carry reason/step")

    @classmethod
    def succeeded(cls) -> "Outcome":
        return cls(OutcomeKind.SUCCEEDED)

    @classmethod
    def failed(cls, reason: str, failed_step: str) -> "Outcome":
        return cls(OutcomeKind.FAILED, reason=reason, failed_step=failed_step)

    @classmethod
    def cancelled(cls, reason: Optional[str] = None) -> "Outcome":
        # Cancelled is allowed without reason, but step is optional.
        return cls(OutcomeKind.CANCELLED, reason=reason, failed_step=None)


class ExtractionPath(str, Enum):
    LLM = "llm"
    REGEX = "regex"
    DEFAULT = "default"


@dataclass(frozen=True)
class ExtractedIntent:
    """Structured result of intent extraction."""

    app_name: AppName
    stack: "StackName"
    description: AppDescription
    extraction_path: ExtractionPath


# --------------------------------------------------------------------------- #
# Time / identity
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CorrelationId:
    """A UUIDv4 (canonical string) identifying an OnboardingRun.

    Strictly v4: rejects v1 to avoid leaking the host MAC address.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError(
                f"CorrelationId.value must be str, got {type(self.value).__name__}"
            )
        try:
            parsed = uuid.UUID(self.value)
        except ValueError as exc:
            raise ValueError(f"Invalid CorrelationId: {self.value!r}") from exc
        if parsed.version != 4:
            raise ValueError(
                f"CorrelationId requires UUIDv4, got v{parsed.version}: {self.value!r}"
            )

    @classmethod
    def new(cls) -> "CorrelationId":
        return cls(str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Timestamp:
    """A timezone-aware UTC timestamp."""

    value: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, datetime):
            raise TypeError("Timestamp.value must be a datetime")
        if self.value.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (UTC)")

    @classmethod
    def now(cls) -> "Timestamp":
        return cls(datetime.now(tz=timezone.utc))

    def isoformat(self) -> str:
        return self.value.isoformat()


# --------------------------------------------------------------------------- #
# Stack catalog
# --------------------------------------------------------------------------- #

_STACK_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")


@dataclass(frozen=True)
class StackName:
    value: str

    def __post_init__(self) -> None:
        if not _STACK_NAME_RE.fullmatch(self.value):
            raise ValueError(f"Invalid StackName: {self.value!r}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class StackVersion:
    value: str

    _SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$")

    def __post_init__(self) -> None:
        if not self._SEMVER.fullmatch(self.value):
            raise ValueError(f"Invalid StackVersion (must be semver): {self.value!r}")


@dataclass(frozen=True)
class TemplatePath:
    value: Path

    def __post_init__(self) -> None:
        # Coerce strings into Path for ergonomic call sites.
        if isinstance(self.value, str):
            object.__setattr__(self, "value", Path(self.value))
        if not isinstance(self.value, Path):
            raise TypeError(
                f"TemplatePath must be Path or str, got {type(self.value).__name__}"
            )


@dataclass(frozen=True)
class TemplateVariableSet:
    """Frozen set of variable names declared by a Stack template."""

    values: FrozenSet[str]

    def __post_init__(self) -> None:
        if not isinstance(self.values, frozenset):
            object.__setattr__(self, "values", frozenset(self.values))
        for v in self.values:
            if not isinstance(v, str) or not v:
                raise ValueError(f"Invalid template variable name: {v!r}")

    def __contains__(self, name: object) -> bool:
        return name in self.values

    def __iter__(self):
        return iter(self.values)


@dataclass(frozen=True)
class RenderedFile:
    """One rendered file: relative POSIX path + bytes content.

    Tuple-unpackable as ``(relative_path, content)`` for ergonomic iteration.
    """

    relative_path: str
    content: bytes

    def __post_init__(self) -> None:
        if "\\" in self.relative_path or self.relative_path.startswith("/"):
            raise ValueError(
                f"RenderedFile.relative_path must be a relative POSIX path, got "
                f"{self.relative_path!r}"
            )
        if not isinstance(self.content, (bytes, bytearray)):
            raise TypeError("RenderedFile.content must be bytes")

    def __iter__(self):
        yield self.relative_path
        yield self.content


# --------------------------------------------------------------------------- #
# VCS / Git
# --------------------------------------------------------------------------- #

_REPO_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?)"
    r"/(?P<name>[A-Za-z0-9._-]{1,100})\.git$"
)


@dataclass(frozen=True)
class RepositoryUrl:
    """Canonical HTTPS GitHub clone URL ending in .git."""

    value: str

    def __post_init__(self) -> None:
        if not _REPO_URL_RE.fullmatch(self.value):
            raise ValueError(f"Invalid RepositoryUrl: {self.value!r}")

    @classmethod
    def from_app(
        cls, app_name: "AppName", kind: str, owner: str
    ) -> "RepositoryUrl":
        """Build the canonical URL ``https://github.com/<owner>/<app>-<kind>.git``."""
        if kind not in ("source", "gitops"):
            raise ValueError(f"kind must be 'source' or 'gitops', got {kind!r}")
        return cls(f"https://github.com/{owner}/{app_name.value}-{kind}.git")

    @property
    def owner(self) -> str:
        m = _REPO_URL_RE.fullmatch(self.value)
        assert m is not None  # validated in __post_init__
        return m.group("owner")

    @property
    def repo_name(self) -> str:
        m = _REPO_URL_RE.fullmatch(self.value)
        assert m is not None
        return m.group("name")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class BranchName:
    value: str = "main"

    def __post_init__(self) -> None:
        if not self.value or any(c.isspace() for c in self.value):
            raise ValueError(f"Invalid BranchName: {self.value!r}")


@dataclass(frozen=True)
class CommitMessage:
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("CommitMessage must not be empty")
        first = self.value.splitlines()[0]
        if len(first) > 100:
            raise ValueError("CommitMessage subject line must be ≤ 100 chars")


@dataclass(frozen=True)
class GitSha:
    value: str

    _RE = re.compile(r"^[0-9a-f]{7,40}$")

    def __post_init__(self) -> None:
        if not self._RE.fullmatch(self.value):
            raise ValueError(f"Invalid GitSha: {self.value!r}")

    def short(self) -> str:
        return self.value[:7]


class RepoStatus(str, Enum):
    EMPTY = "empty"
    POPULATED = "populated"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# GitOps / Kubernetes
# --------------------------------------------------------------------------- #

class ManifestKind(str, Enum):
    NAMESPACE = "Namespace"
    DEPLOYMENT = "Deployment"
    SERVICE = "Service"
    INGRESS = "Ingress"
    CONFIGMAP = "ConfigMap"
    KUSTOMIZATION = "Kustomization"
    SERVICEMONITOR = "ServiceMonitor"
    NETWORKPOLICY = "NetworkPolicy"
    RESOURCEQUOTA = "ResourceQuota"
    EXTERNALSECRET = "ExternalSecret"
    APPLICATION = "Application"


@dataclass(frozen=True)
class ImageTag:
    value: str

    _RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")

    def __post_init__(self) -> None:
        if not self._RE.fullmatch(self.value):
            raise ValueError(f"Invalid ImageTag: {self.value!r}")


@dataclass(frozen=True)
class ContainerImage:
    registry: str
    repository: str
    tag: ImageTag

    def __post_init__(self) -> None:
        if "/" in self.registry or not self.registry:
            raise ValueError(f"Invalid registry: {self.registry!r}")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", self.repository):
            raise ValueError(f"Invalid repository: {self.repository!r}")

    def __str__(self) -> str:
        return f"{self.registry}/{self.repository}:{self.tag.value}"

    @property
    def warns_on_latest(self) -> bool:
        return self.tag.value == "latest"


@dataclass(frozen=True)
class ReplicaCount:
    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise TypeError("ReplicaCount must be an int")
        if self.value < 0:
            raise ValueError("ReplicaCount must be ≥ 0")


# --------------------------------------------------------------------------- #
# ArgoCD
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ArgoProjectName:
    value: str = "default"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9-]{1,63}", self.value):
            raise ValueError(f"Invalid ArgoProjectName: {self.value!r}")


@dataclass(frozen=True)
class ClusterServer:
    value: str = "https://kubernetes.default.svc"

    def __post_init__(self) -> None:
        if not self.value.startswith(("http://", "https://")):
            raise ValueError(f"Invalid ClusterServer URL: {self.value!r}")


@dataclass(frozen=True)
class ArgoSource:
    repo_url: RepositoryUrl
    target_revision: str = "HEAD"
    path: str = "."


@dataclass(frozen=True)
class ArgoDestination:
    server: ClusterServer
    namespace: Namespace


@dataclass(frozen=True)
class SyncPolicy:
    automated: bool = True
    prune: bool = True
    self_heal: bool = True
    create_namespace: bool = True
    server_side_apply: bool = True


class SyncStatus(str, Enum):
    SYNCED = "Synced"
    OUT_OF_SYNC = "OutOfSync"
    UNKNOWN = "Unknown"


class HealthStatus(str, Enum):
    HEALTHY = "Healthy"
    PROGRESSING = "Progressing"
    DEGRADED = "Degraded"
    SUSPENDED = "Suspended"
    MISSING = "Missing"
    UNKNOWN = "Unknown"


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ActorIdentity:
    """Who initiated an action. Used in events and audit."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("ActorIdentity must not be empty")


@dataclass(frozen=True)
class IngressHost:
    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"^[a-z0-9.-]{1,253}$", self.value):
            raise ValueError(f"Invalid IngressHost: {self.value!r}")


@dataclass(frozen=True)
class TemplateVariables:
    """Bag of variables passed to TemplateRenderingService."""

    app_name: AppName
    description: AppDescription
    namespace: Namespace
    host: IngressHost
    replicas: ReplicaCount = field(default_factory=lambda: ReplicaCount(2))
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "appName": self.app_name.value,
            "description": self.description.text,
            "namespace": self.namespace.value,
            "host": self.host.value,
            "replicas": self.replicas.value,
        }
        d.update(self.extra)
        return d
