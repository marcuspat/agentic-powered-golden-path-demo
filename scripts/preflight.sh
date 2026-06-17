#!/usr/bin/env bash
# scripts/preflight.sh â Pre-demo validator
# Fail fast with actionable errors before running the demo.
# Exit 0 = all clear. Exit 1 = one or more blockers.
set -uo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "  ${GREEN}â${NC} $*"; }
fail() { echo -e "  ${RED}â${NC} $*"; FAILED=1; }
warn() { echo -e "  ${YELLOW}â ï¸ ${NC} $*"; }

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo -e "\n${BLUE}=== Golden Path Pre-flight Check ===${NC}\n"

FAILED=0

# âââ 1. Required env vars âââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo -e "${BLUE}ââ Environment Variables${NC}"

check_env() {
  local var="$1"
  local hint="$2"
  if [[ -n "${!var:-}" ]]; then
    local val="${!var}"
    ok "$var is set (${val:0:4}****)"
  else
    fail "$var is not set  â  $hint"
  fi
}

check_env GITHUB_TOKEN      "export GITHUB_TOKEN=ghp_..."
check_env GITHUB_USERNAME   "export GITHUB_USERNAME=your_username"
check_env OPENROUTER_API_KEY "export OPENROUTER_API_KEY=sk-or-..."

# âââ 2. Required CLI tools ââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ CLI Tools${NC}"

check_cmd() {
  local cmd="$1"
  local hint="${2:-install $cmd}"
  if command -v "$cmd" &>/dev/null; then
    ok "$cmd ($(command -v "$cmd"))"
  else
    fail "$cmd not found  â  $hint"
  fi
}

check_cmd git    "brew install git"
check_cmd python3 "brew install python"
check_cmd kubectl "brew install kubectl"
check_cmd docker  "https://docs.docker.com/get-docker/"

# Check idpbuilder binary
if [[ -x "$REPO_ROOT/idpbuilder" ]]; then
  ok "idpbuilder binary present"
else
  fail "idpbuilder binary missing  â  run 'make setup'"
fi

# âââ 3. Docker daemon âââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ Docker${NC}"

if docker info &>/dev/null 2>&1; then
  ok "Docker daemon is running"
else
  fail "Docker daemon is not running  â  start Docker Desktop"
fi

# âââ 4. Kubernetes cluster ââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ Kubernetes Cluster${NC}"

if kubectl cluster-info &>/dev/null 2>&1; then
  CLUSTER_NAME="$(kubectl config current-context 2>/dev/null || echo 'unknown')"
  ok "kubectl connected to: $CLUSTER_NAME"
else
  fail "kubectl cannot reach cluster  â  run 'make bootstrap'"
fi

# âââ 5. ArgoCD namespace ââââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ ArgoCD${NC}"

if kubectl get namespace argocd &>/dev/null 2>&1; then
  ok "argocd namespace exists"

  # Check at least one argocd pod is Running
  RUNNING_PODS="$(kubectl get pods -n argocd --field-selector=status.phase=Running \
    --no-headers 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$RUNNING_PODS" -gt 0 ]]; then
    ok "$RUNNING_PODS ArgoCD pod(s) running"
  else
    warn "ArgoCD namespace exists but no pods are Running yet (may still be starting)"
  fi
else
  fail "argocd namespace not found  â  run 'make bootstrap'"
fi

# âââ 6. Python dependencies âââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ Python Dependencies${NC}"

check_py_import() {
  local module="$1"
  local pkg="${2:-$1}"
  if python3 -c "import $module" &>/dev/null 2>&1; then
    ok "python: $module"
  else
    fail "python: $module not installed  â  pip install $pkg"
  fi
}

check_py_import github   "PyGithub"
check_py_import jinja2   "Jinja2"
check_py_import requests "requests"
check_py_import dotenv   "python-dotenv"
check_py_import kubernetes "kubernetes"

# openai is optional (falls back to regex)
if python3 -c "import openai" &>/dev/null 2>&1; then
  ok "python: openai (AI extraction enabled)"
else
  warn "python: openai not installed (falling back to regex extraction)  â  pip install openai"
fi

# âââ 7. Stack template directories âââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ Stack Templates${NC}"

check_dir() {
  local path="$1"
  local label="$2"
  if [[ -d "$path" ]]; then
    ok "$label ($path)"
  else
    fail "$label not found  â  $path"
  fi
}

check_dir "$REPO_ROOT/cnoe-stacks/nodejs-template/app-source"   "NodeJS app template"
check_dir "$REPO_ROOT/cnoe-stacks/nodejs-gitops-template"        "GitOps template"

# âââ 8. GitHub Token Validation âââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}ââ GitHub API Connectivity${NC}"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  HTTP_STATUS="$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    https://api.github.com/user 2>/dev/null || echo "000")"

  if [[ "$HTTP_STATUS" == "200" ]]; then
    GH_LOGIN="$(curl -sf -H "Authorization: token $GITHUB_TOKEN" \
      https://api.github.com/user 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('login','?'))" 2>/dev/null || echo '?')"
    ok "GitHub API reachable, authenticated as: $GH_LOGIN"
  elif [[ "$HTTP_STATUS" == "401" ]]; then
    fail "GITHUB_TOKEN is invalid or expired (HTTP 401)"
  else
    warn "GitHub API check returned HTTP $HTTP_STATUS (may be rate-limited or no internet)"
  fi
fi

# âââ Summary ââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââââ
echo ""
echo -e "${BLUE}âââââââââââââââââââââââââââââââââââââ${NC}"
if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}â All pre-flight checks passed. Ready to run 'make demo'.${NC}\n"
  exit 0
else
  echo -e "${RED}â Pre-flight checks failed. Fix the errors above and re-run 'make preflight'.${NC}\n"
  exit 1
fi
