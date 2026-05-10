#!/usr/bin/env bash
#
# Golden Path demo bring-up.
#
# Stands up the local IDP stack used by the demo:
#
#   1. Verifies prerequisites (Docker, kubectl, idpbuilder, env vars).
#   2. Creates the cluster and core stacks via ``./idpbuilder create``.
#   3. Waits for ArgoCD to report Healthy.
#   4. Prints credentials and the URLs the demo presenter needs.
#
# Usage:
#   ./scripts/deploy-demo.sh
#
# Env (per ADR-0014):
#   GITHUB_TOKEN         (required) PAT for repo creation
#   GITHUB_USERNAME      (required) Owner namespace for created repos
#   OPENROUTER_API_KEY   (required) LLM access for the agent
#   ARGOCD_NAMESPACE     (optional) default: argocd
#   IDPBUILDER_BIN       (optional) default: $REPO_ROOT/idpbuilder
#   ARGOCD_TIMEOUT       (optional) seconds; default: 600
#
# Exit codes:
#   0  Success.
#   2  Usage / pre-flight failure.
#   3  idpbuilder create failed.
#   4  ArgoCD never reached Healthy within ARGOCD_TIMEOUT.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
IDPBUILDER_BIN="${IDPBUILDER_BIN:-$REPO_ROOT/idpbuilder}"
ARGOCD_TIMEOUT="${ARGOCD_TIMEOUT:-600}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
    _RED=$'\033[0;31m'; _GREEN=$'\033[0;32m'; _YELLOW=$'\033[1;33m'
    _BLUE=$'\033[0;34m'; _BOLD=$'\033[1m'; _RESET=$'\033[0m'
else
    _RED=""; _GREEN=""; _YELLOW=""; _BLUE=""; _BOLD=""; _RESET=""
fi

step()    { echo; echo "${_BLUE}${_BOLD}== $* ==${_RESET}"; }
log_ok()  { echo "${_GREEN}OK${_RESET}: $*"; }
log_warn(){ echo "${_YELLOW}WARN${_RESET}: $*" >&2; }
log_err() { echo "${_RED}ERROR${_RESET}: $*" >&2; }

trap 'log_err "Deployment interrupted at: ${BASH_COMMAND}"' ERR

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

check_prereqs() {
    step "Verifying prerequisites"

    local required_tools=(docker kubectl)
    local missing_tools=()
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" >/dev/null 2>&1; then
            missing_tools+=("$tool")
        fi
    done
    if (( ${#missing_tools[@]} )); then
        log_err "Missing required tools on PATH: ${missing_tools[*]}"
        exit 2
    fi
    log_ok "Tools present: ${required_tools[*]}"

    if ! docker info >/dev/null 2>&1; then
        log_err "Docker daemon is not running or not accessible."
        exit 2
    fi
    log_ok "Docker daemon is reachable."

    if [[ ! -x "$IDPBUILDER_BIN" ]]; then
        log_err "idpbuilder not found or not executable: $IDPBUILDER_BIN"
        log_err "Override with IDPBUILDER_BIN=/path/to/idpbuilder."
        exit 2
    fi
    log_ok "idpbuilder binary: $IDPBUILDER_BIN"

    local missing_env=()
    for var in GITHUB_TOKEN GITHUB_USERNAME OPENROUTER_API_KEY; do
        if [[ -z "${!var:-}" ]]; then
            missing_env+=("$var")
        fi
    done
    if (( ${#missing_env[@]} )); then
        log_err "Missing required env vars (ADR-0014): ${missing_env[*]}"
        exit 2
    fi
    log_ok "Required env vars present (values not echoed)."
}

# ---------------------------------------------------------------------------
# idpbuilder create
# ---------------------------------------------------------------------------

run_idpbuilder() {
    step "Running idpbuilder create"
    if ! "$IDPBUILDER_BIN" create; then
        log_err "idpbuilder create failed."
        exit 3
    fi
    log_ok "idpbuilder create finished."
}

# ---------------------------------------------------------------------------
# ArgoCD readiness
# ---------------------------------------------------------------------------

wait_for_argocd() {
    step "Waiting for ArgoCD to report Healthy (timeout ${ARGOCD_TIMEOUT}s)"

    if ! kubectl get namespace "$ARGOCD_NAMESPACE" >/dev/null 2>&1; then
        log_err "ArgoCD namespace not found: $ARGOCD_NAMESPACE"
        exit 4
    fi

    if ! kubectl wait --for=condition=available \
        --timeout="${ARGOCD_TIMEOUT}s" \
        -n "$ARGOCD_NAMESPACE" \
        deployment/argocd-server; then
        log_err "argocd-server deployment did not become available within ${ARGOCD_TIMEOUT}s."
        kubectl -n "$ARGOCD_NAMESPACE" get pods >&2 || true
        exit 4
    fi
    log_ok "argocd-server is available."
}

# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

print_credentials() {
    step "Demo credentials & URLs"

    local pw=""
    if pw=$(kubectl -n "$ARGOCD_NAMESPACE" get secret argocd-initial-admin-secret \
            -o jsonpath='{.data.password}' 2>/dev/null) && [[ -n "$pw" ]]; then
        pw=$(printf '%s' "$pw" | base64 --decode)
        echo "ArgoCD username: admin"
        echo "ArgoCD password: $pw"
    else
        log_warn "Could not read argocd-initial-admin-secret; ArgoCD may already be initialised."
    fi

    cat <<EOF

Useful commands:
  ArgoCD UI port-forward:
    kubectl port-forward -n $ARGOCD_NAMESPACE svc/argocd-server 8080:443
  Cluster overview:
    kubectl get pods -A
  Onboard an app via the agent:
    make agent-cli REQUEST="onboard inventory-api"
  Roll back an app:
    ./scripts/rollback.sh <app-name>

EOF
    log_ok "Demo bring-up complete."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    local started=$SECONDS
    check_prereqs
    run_idpbuilder
    wait_for_argocd
    print_credentials
    local elapsed=$(( SECONDS - started ))
    echo "${_GREEN}Total elapsed: ${elapsed}s${_RESET}"
}

main "$@"
