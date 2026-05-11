"""CLI transport for the agent.

Forms::

    python -m agent "<request>"                          # onboard
    python -m agent onboard "<request>"                  # explicit
    python -m agent cleanup <app-name> [--repos] [--keep-namespace]
    python -m agent --validate-env
    python -m agent --version

Exit codes (per ``docs/ddd/10-application-services.md``):

- 0 — operation succeeded
- 1 — operation failed
- 2 — cancelled or usage error
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List, Optional, Sequence

from agent import __version__
from agent.application.cleanup import CleanupCommand, CleanupResult
from agent.application.onboarding import (
    OnboardingApplicationService,
    OnboardingCommand,
    OnboardingOptions,
    OnboardingResult,
)
from agent.composition import (
    build_cleanup_service,
    build_onboarding_service,
)
from agent.domain.values import ActorIdentity, AppName, OutcomeKind

logger = logging.getLogger("agent")

ONBOARDING_REQUIRED = ("GITHUB_TOKEN", "GITHUB_USERNAME", "OPENROUTER_API_KEY")
CLEANUP_REQUIRED = ("GITHUB_USERNAME",)


# --------------------------------------------------------------------------- #
# argparse
# --------------------------------------------------------------------------- #

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent",
        description="Golden Path AI-powered onboarding agent",
    )
    p.add_argument("--version", action="store_true", help="Print version and exit")
    p.add_argument("--validate-env", action="store_true",
                   help="Check required env vars and exit")
    p.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"),
                   help="Python logging level (default INFO)")

    sub = p.add_subparsers(dest="command")

    # onboard (also the default when a bare string is passed)
    onb = sub.add_parser("onboard", help="Onboard a new application")
    onb.add_argument("request", help="Natural-language onboarding request")
    onb.add_argument("--no-llm", action="store_true",
                     help="Skip OpenRouter; use the regex/default extractor")
    onb.add_argument("--dry-run", action="store_true",
                     help="Parse and validate but do not provision")
    onb.add_argument("--actor", default="developer@local",
                     help="Identity of the requester for audit/logs")

    # cleanup
    cln = sub.add_parser("cleanup", help="Tear down an onboarded application")
    cln.add_argument("app_name", help="Application name (DNS-safe slug)")
    cln.add_argument("--repos", action="store_true",
                     help="Also delete the source + gitops GitHub repositories")
    cln.add_argument("--keep-namespace", action="store_true",
                     help="Do not delete the Kubernetes namespace")
    cln.add_argument("--namespace", default=None,
                     help="Override the namespace (default: <app-name>)")
    cln.add_argument("--actor", default="operator@local",
                     help="Identity of the operator for audit/logs")

    return p


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = _build_parser()
    argv = list(argv) if argv is not None else sys.argv[1:]
    # Back-compat: bare string (no subcommand) → onboard.
    known = {"onboard", "cleanup"}
    has_flag_only = all(a.startswith("-") for a in argv) if argv else False
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        argv = ["onboard", *argv]
    args = parser.parse_args(argv)
    if not args.command and not (args.version or args.validate_env):
        parser.error("a subcommand or a free-text request is required")
    return args


# --------------------------------------------------------------------------- #
# env-var validation
# --------------------------------------------------------------------------- #

def _missing(varnames: Sequence[str]) -> List[str]:
    return [v for v in varnames if not os.environ.get(v)]


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

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
        missing = _missing(ONBOARDING_REQUIRED)
        if missing:
            print(f"Missing env vars: {missing}", file=sys.stderr)
            return 2
        print("OK")
        return 0

    if args.command == "onboard":
        return _run_onboard(args)
    if args.command == "cleanup":
        return _run_cleanup(args)
    print("unknown command", file=sys.stderr)
    return 2


def _run_onboard(args: argparse.Namespace) -> int:
    if not args.request:
        print("usage: agent onboard \"<request>\"", file=sys.stderr)
        return 2

    required = (
        ("GITHUB_TOKEN", "GITHUB_USERNAME")
        if args.no_llm
        else ONBOARDING_REQUIRED
    )
    missing = _missing(required)
    if missing and not args.dry_run:
        print(f"Missing env vars: {missing}", file=sys.stderr)
        return 2

    service: OnboardingApplicationService = build_onboarding_service(
        enable_llm=not args.no_llm,
    )
    command = OnboardingCommand(
        request_text=args.request,
        actor=ActorIdentity(args.actor),
        options=OnboardingOptions(dry_run=args.dry_run),
    )
    result = service.run(command)
    _print_onboard_result(result)
    if result.outcome.kind is OutcomeKind.SUCCEEDED:
        return 0
    if result.outcome.kind is OutcomeKind.CANCELLED:
        return 2
    return 1


def _run_cleanup(args: argparse.Namespace) -> int:
    try:
        app_name = AppName(args.app_name)
    except ValueError as exc:
        print(f"Invalid app name: {exc}", file=sys.stderr)
        return 2

    missing = _missing(CLEANUP_REQUIRED) if args.repos else []
    if missing:
        print(f"Missing env vars: {missing}", file=sys.stderr)
        return 2

    service = build_cleanup_service()
    namespace = None
    if args.namespace:
        from agent.domain.values import Namespace
        try:
            namespace = Namespace(args.namespace)
        except ValueError as exc:
            print(f"Invalid namespace: {exc}", file=sys.stderr)
            return 2

    result = service.cleanup(
        CleanupCommand(
            app_name=app_name,
            actor=ActorIdentity(args.actor),
            delete_repos=args.repos,
            keep_namespace=args.keep_namespace,
            namespace=namespace,
        )
    )
    _print_cleanup_result(result)
    return 0 if result.succeeded else 1


# --------------------------------------------------------------------------- #
# pretty-printing
# --------------------------------------------------------------------------- #

def _print_onboard_result(result: OnboardingResult) -> None:
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


def _print_cleanup_result(result: CleanupResult) -> None:
    if result.succeeded:
        print(f"✅ Cleanup completed for {result.app_name}")
    else:
        print(f"❌ Cleanup encountered errors for {result.app_name}", file=sys.stderr)
    print(f"   correlation_id: {result.correlation_id}")
    if result.steps_taken:
        print("   steps:")
        for step in result.steps_taken:
            print(f"     - {step}")
    if result.skipped:
        print("   skipped:")
        for s in result.skipped:
            print(f"     - {s}")
    if result.errors:
        print("   errors:", file=sys.stderr)
        for e in result.errors:
            print(f"     - {e}", file=sys.stderr)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
