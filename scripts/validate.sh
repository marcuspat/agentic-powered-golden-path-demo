#!/usr/bin/env bash
#
# Golden Path validation gauntlet.
#
# Runs lint, typecheck, the unit + integration + security tiers, and reports
# the first failing stage. Used as the local pre-push gate and as the body
# of the ``validate`` Makefile target.
#
# Usage:
#   ./scripts/validate.sh           # run everything
#   ./scripts/validate.sh --quick   # skip typecheck + security
#
# Exit codes:
#   0  All stages passed.
#   1+ The exit code of the first failing stage.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

if [[ -t 1 ]]; then
    _RED=$'\033[0;31m'; _GREEN=$'\033[0;32m'; _YELLOW=$'\033[1;33m'
    _BLUE=$'\033[0;34m'; _BOLD=$'\033[1m'; _RESET=$'\033[0m'
else
    _RED=""; _GREEN=""; _YELLOW=""; _BLUE=""; _BOLD=""; _RESET=""
fi

stage_banner() { echo "${_BLUE}${_BOLD}== $* ==${_RESET}"; }
ok()           { echo "${_GREEN}OK${_RESET}: $*"; }
warn()         { echo "${_YELLOW}WARN${_RESET}: $*" >&2; }
fail()         { echo "${_RED}FAIL${_RESET}: $*" >&2; }

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------

QUICK=0
for arg in "$@"; do
    case "$arg" in
        --quick) QUICK=1 ;;
        -h|--help)
            sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *)
            fail "Unknown argument: $arg"
            exit 2 ;;
    esac
done

cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
PYTEST="$PYTHON -m pytest"

# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

CURRENT_STAGE="setup"

run_stage() {
    local name="$1"; shift
    CURRENT_STAGE="$name"
    stage_banner "$name"
    if "$@"; then
        ok "$name"
    else
        local rc=$?
        fail "Validation failed at stage: $name (exit $rc)"
        exit "$rc"
    fi
}

# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

# Lint — every run.
run_stage "lint" $PYTHON -m ruff check agent/ tests/

# Typecheck — skipped in --quick.
if (( QUICK )); then
    warn "Skipping typecheck (--quick)"
else
    run_stage "typecheck" $PYTHON -m mypy agent/
fi

# Unit + integration tiers — every run.
run_stage "unit" $PYTEST tests/unit -q -m "not legacy"
run_stage "integration" $PYTEST tests/integration -q -m "not legacy"

# Security tier — skipped in --quick.
if (( QUICK )); then
    warn "Skipping security tier (--quick)"
else
    run_stage "security" $PYTEST tests/security -q
fi

echo
echo "${_GREEN}${_BOLD}All validations passed.${_RESET}"
