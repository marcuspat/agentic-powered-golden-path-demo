#!/usr/bin/env bash
#
# Golden Path rollback wrapper — implements ADR-0019.
#
# This script is the canonical, declarative rollback for an onboarded app.
# It clones the app's *-gitops repository, reverts the bad commit, and
# pushes — ArgoCD then re-syncs to the previous-good manifests.
#
# Usage:
#   ./scripts/rollback.sh <app-name> [<gitops-repo-url>]
#
# Options:
#   -c <sha>   Revert <sha> instead of HEAD.
#   --yes      Skip the interactive confirmation prompt.
#   -h, --help Show usage.
#
# Environment:
#   GITHUB_USERNAME   Used to derive the default gitops URL when none is given.
#
# Exit codes:
#   0  Success.
#   2  Usage error.
#   3  Pre-flight failure (missing tool, env var, repo, or commit).
#   4  Revert/push failed.

set -euo pipefail

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
    _RED=$'\033[0;31m'; _GREEN=$'\033[0;32m'; _YELLOW=$'\033[1;33m'
    _BLUE=$'\033[0;34m'; _RESET=$'\033[0m'
else
    _RED=""; _GREEN=""; _YELLOW=""; _BLUE=""; _RESET=""
fi

log_info()    { echo "${_BLUE}[INFO]${_RESET} $*"; }
log_ok()      { echo "${_GREEN}[OK]${_RESET} $*"; }
log_warn()    { echo "${_YELLOW}[WARN]${_RESET} $*" >&2; }
log_error()   { echo "${_RED}[ERROR]${_RESET} $*" >&2; }

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

usage() {
    cat >&2 <<'EOF'
Usage: rollback.sh <app-name> [<gitops-repo-url>] [-c <sha>] [--yes]

Reverts the most recent commit (or -c <sha>) on <app>-gitops and pushes,
triggering ArgoCD to re-sync to the previous-good manifests (ADR-0019).

Arguments:
  <app-name>          The DNS-label name of the onboarded application.
  <gitops-repo-url>   Optional. Defaults to
                      https://github.com/$GITHUB_USERNAME/<app>-gitops.git

Options:
  -c <sha>            Revert <sha> instead of HEAD.
  --yes               Skip the confirmation prompt.
  -h, --help          Show this help.

Examples:
  ./scripts/rollback.sh inventory-api
  ./scripts/rollback.sh inventory-api --yes
  ./scripts/rollback.sh inventory-api -c deadbeef
  ./scripts/rollback.sh inventory-api https://github.com/me/inv-gitops.git --yes
EOF
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

APP_NAME=""
GITOPS_URL=""
TARGET_SHA="HEAD"
ASSUME_YES=0

while (( $# )); do
    case "$1" in
        -h|--help)
            usage; exit 0 ;;
        --yes)
            ASSUME_YES=1; shift ;;
        -c)
            [[ $# -ge 2 ]] || { log_error "-c requires an argument"; usage; exit 2; }
            TARGET_SHA="$2"; shift 2 ;;
        -*)
            log_error "Unknown flag: $1"; usage; exit 2 ;;
        *)
            if [[ -z "$APP_NAME" ]]; then
                APP_NAME="$1"
            elif [[ -z "$GITOPS_URL" ]]; then
                GITOPS_URL="$1"
            else
                log_error "Unexpected positional argument: $1"; usage; exit 2
            fi
            shift ;;
    esac
done

if [[ -z "$APP_NAME" ]]; then
    log_error "<app-name> is required"
    usage
    exit 2
fi

if [[ -z "$GITOPS_URL" ]]; then
    if [[ -z "${GITHUB_USERNAME:-}" ]]; then
        log_error "GITHUB_USERNAME not set; cannot derive default gitops URL."
        log_error "Pass <gitops-repo-url> explicitly or export GITHUB_USERNAME."
        exit 3
    fi
    GITOPS_URL="https://github.com/${GITHUB_USERNAME}/${APP_NAME}-gitops.git"
fi

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

for tool in git; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        log_error "Required tool not found on PATH: $tool"
        exit 3
    fi
done

# ---------------------------------------------------------------------------
# Workspace
# ---------------------------------------------------------------------------

WORK_DIR="$(mktemp -d -t gp-rollback-XXXXXX)"
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

log_info "Cloning $GITOPS_URL into $WORK_DIR"
if ! git clone --quiet "$GITOPS_URL" "$WORK_DIR/gitops"; then
    log_error "git clone failed for $GITOPS_URL"
    exit 3
fi

cd "$WORK_DIR/gitops"

# Resolve the target commit (HEAD or user-supplied).
if ! REVERT_SHA=$(git rev-parse --verify "$TARGET_SHA^{commit}" 2>/dev/null); then
    log_error "Cannot resolve commit '$TARGET_SHA' in $GITOPS_URL"
    exit 3
fi

log_info "Last 5 commits on $(git rev-parse --abbrev-ref HEAD):"
git --no-pager log --oneline -5

cat <<EOF

About to revert commit: $REVERT_SHA
Repository:             $GITOPS_URL
App:                    $APP_NAME

ArgoCD will re-sync to the previous-good manifests after the push.
EOF

if (( ! ASSUME_YES )); then
    read -r -p "Proceed with revert and push? [y/N] " reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) log_warn "Aborted by user."; exit 0 ;;
    esac
fi

# ---------------------------------------------------------------------------
# Revert + push
# ---------------------------------------------------------------------------

git config user.email "rollback@golden-path.local"
git config user.name  "Golden Path Rollback"

if ! git revert --no-edit "$REVERT_SHA"; then
    log_error "git revert failed; resolve conflicts manually."
    exit 4
fi

NEW_HEAD=$(git rev-parse HEAD)
log_ok "Created revert commit $NEW_HEAD"

if ! git push origin HEAD; then
    log_error "git push failed."
    exit 4
fi

log_ok "Push succeeded. ArgoCD will pick this up on its next sync."
log_info "If you need an immediate sync, trigger the GitHub -> ArgoCD webhook,"
log_info "or run: argocd app sync ${APP_NAME}"
