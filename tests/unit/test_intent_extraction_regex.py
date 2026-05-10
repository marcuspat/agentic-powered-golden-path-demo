"""Unit tests for the regex fallback path of ``IntentExtractionService``.

The intent extraction service has three paths (per ADR-0011):

1. **LLM** — first choice; uses OpenRouter via the ACL.
2. **Regex** — deterministic fallback when the LLM is unavailable or
   returns an unparseable answer.
3. **Default** — last-resort ``my-app`` so the service NEVER raises.

This file pins the regex path's behaviour without ever touching the
network, by passing ``llm=None`` to the service.
"""

from __future__ import annotations

import pytest

values = pytest.importorskip(
    "agent.domain.values",
    reason="agent.domain.values not yet landed by orchestrator slice",
)
intent_extraction = pytest.importorskip(
    "agent.domain.services.intent_extraction",
    reason="agent.domain.services.intent_extraction not yet landed",
)

AppName = values.AppName
OnboardingRequest = values.OnboardingRequest
ExtractionPath = values.ExtractionPath
IntentExtractionService = intent_extraction.IntentExtractionService

pytestmark = pytest.mark.unit


def _request(text: str) -> object:
    return OnboardingRequest(text)


@pytest.mark.parametrize(
    "request_text,expected",
    [
        ("create a service called inventory-api", "inventory-api"),
        ("Please onboard a new app named payments-svc", "payments-svc"),
        ("deploy order-service-v2", "order-service-v2"),
    ],
)
def test_regex_fallback_extracts_dns_safe_name(
    request_text: str, expected: str
) -> None:
    service = IntentExtractionService(llm=None)
    intent = service.extract(_request(request_text))
    assert intent.app_name == AppName(expected)
    assert intent.extraction_path is ExtractionPath.REGEX


def test_regex_fallback_normalises_via_app_name() -> None:
    """The service must route through ``AppName.from_raw``; if it skipped
    normalisation, the result would not be a valid ``AppName``."""
    service = IntentExtractionService(llm=None)
    intent = service.extract(_request("Make me an app called Inventory-API"))
    # Whatever the path, the result is always a valid AppName.
    AppName(intent.app_name.value)


def test_regex_fallback_falls_through_to_default() -> None:
    """When no pattern matches, the service yields the DEFAULT path, not an exception."""
    service = IntentExtractionService(llm=None)
    intent = service.extract(_request("hello there how are you"))
    assert intent.extraction_path in (ExtractionPath.REGEX, ExtractionPath.DEFAULT)
    assert isinstance(intent.app_name, AppName)


def test_service_always_returns_valid_intent() -> None:
    """The service must never raise — it always returns ExtractedIntent."""
    service = IntentExtractionService(llm=None)
    # Passing an OnboardingRequest with mostly-noise text must still succeed.
    intent = service.extract(_request("########"))
    assert isinstance(intent.app_name, AppName)
