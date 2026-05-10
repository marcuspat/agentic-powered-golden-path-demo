"""CLI transport for the agent.

Usage::

    python -m agent "I need a NodeJS service called inventory-api"
    python -m agent --validate-env
    python -m agent --version

Exit codes (per ``docs/ddd/10-application-services.md``):

- 0 — Onboarding succeeded
- 1 — Onboarding failed
- 2 — Cancelled or usage error
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional, Sequence

from agent import __version__
from agent.application.onboarding import (
    OnboardingApplicationService,
    OnboardingCommand,
    OnboardingOptions,
    OnboardingResult,
)
from agent.composition import build_onboarding_service
from agent.domain.values import ActorIdentity, OutcomeKind

logger = logging.getLogger("agent")

REQUIRED_ENV_VARS = ("GITHUB_TOKEN", "GITHUB_USERNAME", "OPENROUTER_API_KEY")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Golden Path AI-powered onboarding agent",
    )
    parser.add_argument("request", nargs="?", default=None,
                        help="Natural-language onboarding request")
    parser.add_argument("--version", action="store_true",
                        help="Print version and exit")
    parser.add_argument("--validate-env", action="store_true",
                        help="Check required env vars and exit")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip OpenRouter; use the regex/default extractor")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and validate but do not provision")
    parser.add_argument("--actor", default="developer@local",
                        help="Identity of the requester for audit/logs")
    parser.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"),
                        help="Python logging level (default INFO)")
    return parser.parse_args(argv)


def _missing_env_vars() -> List[str]:
    return [v for v in REQUIRED_ENV_VARS if not os.environ.get(v)]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.version:
        print(f"agent {__version__}")
        return 0

    if args.validate_env:
        missing = _missing_env_vars()
        if missing:
            print(f"Missing env vars: {missing}", file=sys.stderr)
            return 2
        print("OK")
        return 0

    if not args.request:
        if args.dry_run:
            print("dry-run requires a request", file=sys.stderr)
            return 2
        print("Usage: agent \"<request>\"  (or --validate-env / --version)",
              file=sys.stderr)
        return 2

    missing = _missing_env_vars() if not args.no_llm else [
        v for v in ("GITHUB_TOKEN", "GITHUB_USERNAME") if not os.environ.get(v)
    ]
    if missing and not args.dry_run:
        print(f"Missing env vars: {missing}", file=sys.stderr)
        return 2

    service: OnboardingApplicationService = build_onboarding_service(enable_llm=not args.no_llm)
    command = OnboardingCommand(
        request_text=args.request,
        actor=ActorIdentity(args.actor),
        options=OnboardingOptions(dry_run=args.dry_run),
    )
    result = service.run(command)
    _print_result(result)
    if result.outcome.kind is OutcomeKind.SUCCEEDED:
        return 0
    if result.outcome.kind is OutcomeKind.CANCELLED:
        return 2
    return 1


def _print_result(result: OnboardingResult) -> None:
    if result.outcome.kind is OutcomeKind.SUCCEEDED:
        print("✅ Onboarding succeeded")
        print(f"   correlation_id: {result.correlation_id}")
        print(f"   app_name:       {result.app_name}")
        print(f"   namespace:      {result.namespace}")
        print(f"   source repo:    {result.source_repo_url}")
        print(f"   gitops repo:    {result.gitops_repo_url}")
        print(f"   ingress:        {result.ingress_url}")
        print(f"   duration:       {result.duration_seconds:.2f}s")
    elif result.outcome.kind is OutcomeKind.CANCELLED:
        print("⚠️  Onboarding cancelled")
        if result.outcome.reason:
            print(f"   reason: {result.outcome.reason}")
    else:
        print("❌ Onboarding failed", file=sys.stderr)
        print(f"   correlation_id: {result.correlation_id}", file=sys.stderr)
        print(f"   step:    {result.outcome.failed_step}", file=sys.stderr)
        print(f"   reason:  {result.outcome.reason}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
