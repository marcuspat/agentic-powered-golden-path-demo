#!/usr/bin/env bash
#
# Tear down a previously-onboarded app.
#
# Usage:
#   ./scripts/cleanup-app.sh <app-name> [--repos] [--yes]
#
# Steps (best-effort, in order):
#   1. Delete the ArgoCD Application named <app-name> from the argocd namespace.
#   2. Delete the namespace <app-name>.
#   3. (Optional, --repos) Delete the source and gitops GitHub repos via ``gh``.
#
# Options:
#   --repos          Also delete the GitHub repos (requires ``gh`` CLI).
#   --yes            Skip the confirmation prompt.
#   -h, --help       Show usage.
#
# Env:
#   ARGOCD_NAMESPACE     Default: argocd.
#   GITHUB_USERNAME      Used when --repos is passed.
#
# Exit codes:
#   0  Success (or nothing to do).
#   2  Usage error.
#   3  Pre-flight failure (missing tool / env var).

set -euo pipefail

if [[ -t 1 ]]; then
    _RED=$'\033[0;31m'; _GREEN=$'\033[0;32m'; _YELLOW=$'\033[1;33m'
    _BLUE=$'\033[0;34m'; _RESET=$'\033[0m'
else
    _RED=""; _GREEN=""; _YELLOW=""; _BLUE=""; _RESET=""
fi

log_info() { echo "${_BLUE}[INFO]${_RESET} $*"; }
log_ok()   { echo "${_GREEN}[OK]${_RESET} $*"; }
log_warn() { echo "${_YELLOW}[WARN]${_RESET} $*" >&2; }
log_err()  { echo "${_RED}[ERROR]${_RESET} $*" >&2; }

usage() {
    sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//' >&2
}

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------

APP_NAME=""
DELETE_REPOS=0
ASSUME_YES=0

while (( $# )); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --repos)   DELETE_REPOS=1; shift ;;
        --yes)     ASSUME_YES=1; shift ;;
        -*)        log_err "Unknown flag: $1"; usage; exit 2 ;;
        *)
            if [[ -z "$APP_NAME" ]]; then
                APP_NAME="$1"
            else
                log_err "Unexpected argument: $1"; usage; exit 2
            fi
            shift ;;
    esac
done

if [[ -z "$APP_NAME" ]]; then
    log_err "<app-name> is required"
    usage
    exit 2
fi

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

if ! command -v kubectl >/dev/null 2>&1; then
    log_err "kubectl is required but not on PATH."
    exit 3
fi

if (( DELETE_REPOS )); then
    if ! command -v gh >/dev/null 2>&1; then
        log_err "--repos requires the gh CLI."
        exit 3
    fi
    if [[ -z "${GITHUB_USERNAME:-}" ]]; then
        log_err "--repos requires GITHUB_USERNAME to be set."
        exit 3
    fi
fi

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"

# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------

cat <<EOF

About to delete:
  ArgoCD Application:  ${APP_NAME} (in ${ARGOCD_NAMESPACE})
  Kubernetes namespace: ${APP_NAME}
EOF

if (( DELETE_REPOS )); then
    cat <<EOF
  GitHub repo:         ${GITHUB_USERNAME}/${APP_NAME}
  GitHub repo:         ${GITHUB_USERNAME}/${APP_NAME}-gitops
EOF
fi

if (( ! ASSUME_YES )); then
    read -r -p "Continue? [y/N] " reply
    case "$reply" in
        y|Y|yes|YES) ;;
        *) log_warn "Aborted by user."; exit 0 ;;
    esac
fi

# ---------------------------------------------------------------------------
# Steps (best-effort: missing resources are not failures)
# ---------------------------------------------------------------------------

log_info "Deleting ArgoCD Application ${APP_NAME}…"
if kubectl -n "$ARGOCD_NAMESPACE" get application "$APP_NAME" >/dev/null 2>&1; then
    kubectl -n "$ARGOCD_NAMESPACE" delete application "$APP_NAME" --wait=false || \
        log_warn "Failed to delete Application; continuing."
    log_ok "Application deletion requested."
else
    log_warn "ArgoCD Application ${APP_NAME} not found; skipping."
fi

log_info "Deleting namespace ${APP_NAME}…"
if kubectl get namespace "$APP_NAME" >/dev/null 2>&1; then
    kubectl delete namespace "$APP_NAME" --wait=false || \
        log_warn "Failed to delete namespace; continuing."
    log_ok "Namespace deletion requested."
else
    log_warn "Namespace ${APP_NAME} not found; skipping."
fi

if (( DELETE_REPOS )); then
    for suffix in "" "-gitops"; do
        local_repo="${GITHUB_USERNAME}/${APP_NAME}${suffix}"
        log_info "Deleting GitHub repo ${local_repo}…"
        if gh repo view "$local_repo" >/dev/null 2>&1; then
            if gh repo delete "$local_repo" --yes >/dev/null 2>&1; then
                log_ok "Deleted ${local_repo}."
            else
                log_warn "gh repo delete failed for ${local_repo} (token may lack delete_repo scope)."
            fi
        else
            log_warn "Repo ${local_repo} not found; skipping."
        fi
    done
fi

log_ok "Cleanup complete for app: ${APP_NAME}"
