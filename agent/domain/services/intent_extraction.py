"""IntentExtractionService — LLM with regex + default fallbacks.

See ADR-0005, ADR-0011, and ``docs/ddd/08-domain-services.md``.
"""
from __future__ import annotations

import logging
import re

from agent.domain.errors import LlmUnavailable
from agent.domain.ports import LlmCompletionPort
from agent.domain.values import (
    AppDescription,
    AppName,
    ExtractedIntent,
    ExtractionPath,
    OnboardingRequest,
    StackName,
)

logger = logging.getLogger(__name__)

DEFAULT_STACK = StackName("nodejs")
DEFAULT_APP_NAME = AppName("my-app")

_PROMPT = """\
Extract the application name from this developer request.

Request: {request!r}

Return ONLY the application name as a lowercase, hyphen-separated slug
(letters, digits, and hyphens only — no spaces, no punctuation).
Examples:
- "I need a new NodeJS service called inventory-api" -> inventory-api
- "Deploy my user-management service" -> user-management
- "Create a payment-processor app" -> payment-processor

Application name:"""


_FALLBACK_PATTERNS = [
    r"called\s+([A-Za-z0-9-]+)",
    r"named\s+([A-Za-z0-9-]+)",
    r"([A-Za-z0-9-]+)\s+service",
    r"([A-Za-z0-9-]+)\s+app",
    r"deploy\s+([A-Za-z0-9-]+)",
    r"create\s+([A-Za-z0-9-]+)",
]


class IntentExtractionService:
    """Convert a request into an ExtractedIntent.

    Strategy chain (ADR-0011): LLM → regex patterns → optional default.

    By default the service is **strict**: if neither the LLM nor the regex
    yields an extractable name, it raises ``ValueError``. Pass
    ``default_app_name=AppName("my-app")`` to get the original ADR-0011
    "always succeeds" behaviour.
    """

    def __init__(
        self,
        llm: LlmCompletionPort | None = None,
        *,
        default_stack: StackName = DEFAULT_STACK,
        default_app_name: AppName | None = DEFAULT_APP_NAME,
    ) -> None:
        self._llm = llm
        self._default_stack = default_stack
        self._default_app_name = default_app_name

    def extract(self, request: OnboardingRequest | str) -> ExtractedIntent:
        # Boundary tolerance: accept raw str or OnboardingRequest.
        text = request.text if hasattr(request, "text") else str(request)

        # 1. Try the LLM. Catch *anything* — the LLM is best-effort and we
        # must never let foreign exceptions leak past the ACL.
        if self._llm is not None:
            try:
                if hasattr(self._llm, "complete"):
                    raw = self._llm.complete(_PROMPT.format(request=text))
                else:
                    raw = None
                if raw:
                    app_name = AppName.from_raw(raw)
                    logger.info("intent.extracted via=llm raw=%r → %s", raw, app_name)
                    return ExtractedIntent(
                        app_name=app_name,
                        stack=self._default_stack,
                        description=AppDescription.for_app(app_name),
                        extraction_path=ExtractionPath.LLM,
                    )
            except (LlmUnavailable, ValueError) as exc:
                logger.warning("intent.llm_failed err=%s — falling back to regex", exc)
            except Exception as exc:  # noqa: BLE001 — boundary safeguard
                logger.warning("intent.llm_unexpected_error err=%s — falling back to regex", exc)

        # 2. Try regex patterns.
        regex_match = _try_regex(text)
        if regex_match is not None:
            logger.info("intent.extracted via=regex → %s", regex_match)
            return ExtractedIntent(
                app_name=regex_match,
                stack=self._default_stack,
                description=AppDescription.for_app(regex_match),
                extraction_path=ExtractionPath.REGEX,
            )

        # 3. Default — only if explicitly opted in.
        if self._default_app_name is not None:
            logger.info("intent.extracted via=default → %s", self._default_app_name)
            return ExtractedIntent(
                app_name=self._default_app_name,
                stack=self._default_stack,
                description=AppDescription.for_app(self._default_app_name),
                extraction_path=ExtractionPath.DEFAULT,
            )
        raise ValueError(
            f"Could not extract an application name from request: {text!r}"
        )


def _try_regex(text: str) -> AppName | None:
    for pattern in _FALLBACK_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return AppName.from_raw(m.group(1))
            except ValueError:
                continue
    return None
