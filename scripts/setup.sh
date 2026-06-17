#!/usr/bin/env bash
# scripts/setup.sh â Platform-aware setup for the Golden Path demo
# Handles: macOS + Linux, amd64 + arm64, idpbuilder download, Python deps
set -euo pipefail

# âââ Colours ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[setup]${NC} $*"; }
error()   { echo -e "${RED}[setup]${NC} $*"; }
section() { echo -e "\n${BLUE}âââ $* âââ${NC}"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# âââ 1. Detect Platform âââââââââââââââââââââââââââââââââââââââââââââââââââââââ
section "Detecting Platform"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"       # darwin | linux
ARCH_RAW="$(uname -m)"                              # x86_64 | arm64 | aarch64
case "$ARCH_RAW" in
  x86_64)           ARCH="amd64" ;;
  arm64 | aarch64)  ARCH="arm64" ;;
  *)                error "Unsupported architecture: $ARCH_RAW"; exit 1 ;;
esac
info "Platform: ${OS}/${ARCH}"

# âââ 2. Check Required Tools ââââââââââââââââââââââââââââââââââââââââââââââââââ
section "Checking Prerequisites"
MISSING=()
for cmd in git docker kubectl python3; do
  if command -v "$cmd" &>/dev/null; then
    info "  â $cmd ($(command -v "$cmd"))"
  else
    error "  â $cmd â not found"
    MISSING+=("$cmd")
  fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
  error "Missing required tools: ${MISSING[*]}"
  echo ""
  echo "Install instructions:"
  for cmd in "${MISSING[@]}"; do
    case "$cmd" in
      docker)   echo "  docker:  https://docs.docker.com/get-docker/" ;;
      kubectl)  echo "  kubectl: brew install kubectl  OR  https://kubernetes.io/docs/tasks/tools/" ;;
      python3)  echo "  python3: brew install python  OR  https://python.org/downloads/" ;;
      git)      echo "  git:     brew install git  OR  https://git-scm.com/downloads" ;;
    esac
  done
  exit 1
fi

# Check Docker is actually running
if ! docker info &>/dev/null; then
  error "Docker daemon is not running. Start Docker Desktop and retry."
  exit 1
fi
info "  â Docker daemon is running"

# Check Python version >= 3.8
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_MAJOR="${PYTHON_VERSION%%.*}"
PYTHON_MINOR="${PYTHON_VERSION#*.}"
if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 8 ]]; then
  error "Python 3.8+ required (found $PYTHON_VERSION)"
  exit 1
fi
info "  â Python $PYTHON_VERSION"

# âââ 3. idpbuilder Binary âââââââââââââââââââââââââââââââââââââââââââââââââââââ
section "idpbuilder Binary"

IDP_BINARY="$REPO_ROOT/idpbuilder"

if [[ -x "$IDP_BINARY" ]]; then
  IDP_VERSION="$("$IDP_BINARY" version 2>/dev/null | head -1 || echo 'unknown')"
  info "  â idpbuilder already present ($IDP_VERSION)"
else
  warn "  idpbuilder binary not found â downloading..."

  IDP_LATEST_TAG="$(curl -sf https://api.github.com/repos/cnoe-io/idpbuilder/releases/latest \
    | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')"

  if [[ -z "$IDP_LATEST_TAG" ]]; then
    error "Could not fetch latest idpbuilder tag from GitHub API. Check your internet connection."
    exit 1
  fi
  info "  Latest tag: $IDP_LATEST_TAG"

  TARBALL="idpbuilder-${OS}-${ARCH}.tar.gz"
  DOWNLOAD_URL="https://github.com/cnoe-io/idpbuilder/releases/download/${IDP_LATEST_TAG}/${TARBALL}"

  info "  Downloading: $DOWNLOAD_URL"
  curl -sL "$DOWNLOAD_URL" -o "/tmp/$TARBALL"
  tar -xzf "/tmp/$TARBALL" idpbuilder -C "$REPO_ROOT"
  chmod +x "$IDP_BINARY"
  rm "/tmp/$TARBALL"

  IDP_VERSION="$("$IDP_BINARY" version 2>/dev/null | head -1 || echo 'installed')"
  info "  â idpbuilder installed ($IDP_VERSION)"
fi

# âââ 4. Python Dependencies âââââââââââââââââââââââââââââââââââââââââââââââââââ
section "Python Dependencies"

# Determine requirements file(s)
REQ_FILES=()
[[ -f "$REPO_ROOT/requirements.txt" ]] && REQ_FILES+=("$REPO_ROOT/requirements.txt")
[[ -f "$REPO_ROOT/ai-onboarding-agent/requirements.txt" ]] && REQ_FILES+=("$REPO_ROOT/ai-onboarding-agent/requirements.txt")

if [[ ${#REQ_FILES[@]} -eq 0 ]]; then
  warn "  No requirements.txt found â skipping pip install"
else
  # Use venv if it exists, otherwise fall back to system pip
  if [[ -f "$REPO_ROOT/.venv/bin/pip" ]]; then
    PIP="$REPO_ROOT/.venv/bin/pip"
    info "  Using venv: $REPO_ROOT/.venv"
  elif [[ -f "$REPO_ROOT/.venv/bin/pip3" ]]; then
    PIP="$REPO_ROOT/.venv/bin/pip3"
  else
    info "  No .venv found â creating one..."
    python3 -m venv "$REPO_ROOT/.venv"
    PIP="$REPO_ROOT/.venv/bin/pip"
    info "  â Created $REPO_ROOT/.venv"
  fi

  for req in "${REQ_FILES[@]}"; do
    info "  Installing from $req..."
    "$PIP" install -q -r "$req"
  done
  info "  â Python dependencies installed"
  info "     Activate venv: source .venv/bin/activate"
fi

# âââ 5. Environment Variable Check ââââââââââââââââââââââââââââââââââââââââââââ
section "Environment Variables"

REQUIRED_VARS=(GITHUB_TOKEN GITHUB_USERNAME OPENROUTER_API_KEY)
ALL_SET=true

for var in "${REQUIRED_VARS[@]}"; do
  if [[ -n "${!var:-}" ]]; then
    # Mask value for display
    VAL="${!var}"
    MASKED="${VAL:0:4}****${VAL: -4}"
    info "  â $var = $MASKED"
  else
    warn "  â ï¸  $var is not set"
    ALL_SET=false
  fi
done

if [[ "$ALL_SET" == "false" ]]; then
  echo ""
  warn "Set missing env vars before running 'make bootstrap' or 'make demo':"
  echo "  export GITHUB_TOKEN=ghp_your_token_here"
  echo "  export GITHUB_USERNAME=your_github_username"
  echo "  export OPENROUTER_API_KEY=sk-or-your_openrouter_key"
  echo ""
  warn "Or copy and fill in the .env example:"
  echo "  cp ai-onboarding-agent/.env.example ai-onboarding-agent/.env"
fi

# âââ Done âââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
info "â Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Set environment variables (see above if any were missing)"
echo "  2. make bootstrap    â spin up the KinD cluster"
echo "  3. make preflight    â validate everything is ready"
echo "  4. make demo         â run the Golden Path demo"
echo ""
