#!/bin/bash

# Golden Path Demo GitOps Validation Script
# This script validates each phase of the GitOps integration workflow

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GITHUB_ORG="${GITHUB_ORG:-your-org}"
SOURCE_REPO="${SOURCE_REPO:-golden-path-demo-source}"
GITOPS_REPO="${GITOPS_REPO:-golden-path-demo-gitops}"
NAMESPACE="${NAMESPACE:-golden-path-demo}"
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validation functions
validate_prerequisites() {
    log_info "Validating prerequisites..."

    # Check if required tools are installed
    local tools=("gh" "kubectl" "argocd" "kustomize" "helm")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "Required tool '$tool' is not installed"
            return 1
        else
            log_success "✓ $tool is installed"
        fi
    done

    # Check GitHub authentication
    if ! gh auth status &> /dev/null; then
        log_error "GitHub CLI is not authenticated. Run 'gh auth login' first."
        return 1
    else
        log_success "✓ GitHub CLI is authenticated"
    fi

    # Check kubernetes cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access Kubernetes cluster"
        return 1
    else
        log_success "✓ Kubernetes cluster is accessible"
    fi

    # Check if ArgoCD is installed
    if ! kubectl get namespace "$ARGOCD_NAMESPACE" &> /dev/null; then
        log_error "ArgoCD namespace '$ARGOCD_NAMESPACE' does not exist"
        return 1
    else
        log_success "✓ ArgoCD namespace exists"
    fi

    log_success "All prerequisites validated"
}

validate_github_repositories() {
    log_info "Validating GitHub repositories..."

    # Check source repository
    if gh repo view "$GITHUB_ORG/$SOURCE_REPO" &> /dev/null; then
        log_success "✓ Source repository exists: $GITHUB_ORG/$SOURCE_REPO"
    else
        log_error "Source repository not found: $GITHUB_ORG/$SOURCE_REPO"
        return 1
    fi

    # Check GitOps repository
    if gh repo view "$GITHUB_ORG/$GITOPS_REPO" &> /dev/null; then
        log_success "✓ GitOps repository exists: $GITHUB_ORG/$GITOPS_REPO"
    else
        log_error "GitOps repository not found: $GITHUB_ORG/$GITOPS_REPO"
        return 1
    fi

    # Check if repositories have the expected structure
    log_info "Checking repository structure..."

    # Clone repositories temporarily to check structure
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" RETURN

    # Check source repository structure
    if gh repo clone "$GITHUB_ORG/$SOURCE_REPO" "$temp_dir/source" &> /dev/null; then
        local source_dirs=("src" "tests" ".github/workflows" "docs")
        for dir in "${source_dirs[@]}"; do
            if [[ -d "$temp_dir/source/$dir" ]]; then
                log_success "✓ Source repo has $dir directory"
            else
                log_warning "Source repo missing $dir directory"
            fi
        done
    fi

    # Check GitOps repository structure
    if gh repo clone "$GITHUB_ORG/$GITOPS_REPO" "$temp_dir/gitops" &> /dev/null; then
        local gitops_dirs=("config/kubernetes" "config/argocd" "config/monitoring")
        for dir in "${gitops_dirs[@]}"; do
            if [[ -d "$temp_dir/gitops/$dir" ]]; then
                log_success "✓ GitOps repo has $dir directory"
            else
                log_warning "GitOps repo missing $dir directory"
            fi
        done
    fi

    log_success "GitHub repositories validated"
}

validate_kubernetes_manifests() {
    log_info "Validating Kubernetes manifests..."

    local manifests=(
        "config/kubernetes/namespace.yaml"
        "config/kubernetes/configmap.yaml"
        "config/kubernetes/deployment.yaml"
        "config/kubernetes/service.yaml"
        "config/kubernetes/ingress.yaml"
        "config/kubernetes/secrets.yaml"
        "config/kubernetes/serviceaccount.yaml"
        "config/kubernetes/hpa.yaml"
        "config/kubernetes/networkpolicy.yaml"
    )

    for manifest in "${manifests[@]}"; do
        if [[ -f "$PROJECT_ROOT/$manifest" ]]; then
            # Validate manifest syntax
            if kubectl apply --dry-run=client -f "$PROJECT_ROOT/$manifest" &> /dev/null; then
                log_success "✓ $manifest syntax is valid"
            else
                log_error "✗ $manifest has syntax errors"
                kubectl apply --dry-run=client -f "$PROJECT_ROOT/$manifest"
                return 1
            fi
        else
            log_error "Manifest not found: $manifest"
            return 1
        fi
    done

    log_success "Kubernetes manifests validated"
}

validate_argocd_applications() {
    log_info "Validating ArgoCD applications..."

    local argocd_manifests=(
        "config/argocd/application.yaml"
        "config/argocd/applicationset.yaml"
        "config/argocd/project.yaml"
    )

    for manifest in "${argocd_manifests[@]}"; do
        if [[ -f "$PROJECT_ROOT/$manifest" ]]; then
            # Validate manifest syntax
            if kubectl apply --dry-run=client -f "$PROJECT_ROOT/$manifest" &> /dev/null; then
                log_success "✓ $manifest syntax is valid"
            else
                log_error "✗ $manifest has syntax errors"
                kubectl apply --dry-run=client -f "$PROJECT_ROOT/$manifest"
                return 1
            fi
        else
            log_error "ArgoCD manifest not found: $manifest"
            return 1
        fi
    done

    # Check if ArgoCD is accessible
    if argocd account get-user-info &> /dev/null; then
        log_success "✓ ArgoCD is accessible"
    else
        log_error "Cannot access ArgoCD server. Check configuration."
        return 1
    fi

    log_success "ArgoCD applications validated"
}

validate_deployment_status() {
    log_info "Validating deployment status..."

    # Check if namespace exists
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_success "✓ Namespace $NAMESPACE exists"
    else
        log_warning "Namespace $NAMESPACE does not exist yet"
        return 0
    fi

    # Check deployment status
    if kubectl get deployment golden-path-demo -n "$NAMESPACE" &> /dev/null; then
        local ready_replicas=$(kubectl get deployment golden-path-demo -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' || echo "0")
        local desired_replicas=$(kubectl get deployment golden-path-demo -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' || echo "0")

        if [[ "$ready_replicas" == "$desired_replicas" ]] && [[ "$desired_replicas" -gt 0 ]]; then
            log_success "✓ Deployment is ready ($ready_replicas/$desired_replicas replicas)"
        else
            log_warning "Deployment not ready ($ready_replicas/$desired_replicas replicas)"
        fi
    else
        log_warning "Deployment not found"
    fi

    # Check service status
    if kubectl get service golden-path-demo-service -n "$NAMESPACE" &> /dev/null; then
        log_success "✓ Service exists"
    else
        log_warning "Service not found"
    fi

    # Check ingress status
    if kubectl get ingress golden-path-demo-ingress -n "$NAMESPACE" &> /dev/null; then
        log_success "✓ Ingress exists"
    else
        log_warning "Ingress not found"
    fi

    # Check pod health
    local pods=$(kubectl get pods -n "$NAMESPACE" -l app=golden-path-demo --no-headers | wc -l)
    if [[ $pods -gt 0 ]]; then
        local healthy_pods=$(kubectl get pods -n "$NAMESPACE" -l app=golden-path-demo --field-selector=status.phase=Running --no-headers | wc -l)
        log_success "✓ $healthy_pods/$pods pods are running"
    else
        log_warning "No pods found"
    fi

    log_success "Deployment status validated"
}

validate_application_connectivity() {
    log_info "Validating application connectivity..."

    # Get ingress hostname
    local ingress_host=$(kubectl get ingress golden-path-demo-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")

    if [[ -z "$ingress_host" ]]; then
        log_warning "Cannot determine ingress hostname"
        return 0
    fi

    log_info "Testing connectivity to https://$ingress_host"

    # Test health endpoint
    if curl -f -s -k "https://$ingress_host/health" &> /dev/null; then
        log_success "✓ Health endpoint is responding"
    else
        log_warning "Health endpoint is not responding"
    fi

    # Test ready endpoint
    if curl -f -s -k "https://$ingress_host/ready" &> /dev/null; then
        log_success "✓ Ready endpoint is responding"
    else
        log_warning "Ready endpoint is not responding"
    fi

    # Test application endpoint
    if curl -f -s -k "https://$ingress_host/api/version" &> /dev/null; then
        log_success "✓ Application API is responding"
    else
        log_warning "Application API is not responding"
    fi

    log_success "Application connectivity validated"
}

validate_monitoring() {
    log_info "Validating monitoring setup..."

    # Check ServiceMonitor
    if kubectl get servicemonitor golden-path-demo -n "$NAMESPACE" &> /dev/null; then
        log_success "✓ ServiceMonitor exists"
    else
        log_warning "ServiceMonitor not found"
    fi

    # Check PrometheusRule
    if kubectl get prometheusrule golden-path-demo-rules -n "$NAMESPACE" &> /dev/null; then
        log_success "✓ PrometheusRule exists"
    else
        log_warning "PrometheusRule not found"
    fi

    # Check if metrics endpoint is accessible
    local ingress_host=$(kubectl get ingress golden-path-demo-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")
    if [[ -n "$ingress_host" ]]; then
        if curl -f -s -k "https://$ingress_host/metrics" | grep -q "http_requests_total" 2>/dev/null; then
            log_success "✓ Metrics endpoint is serving metrics"
        else
            log_warning "Metrics endpoint is not serving expected metrics"
        fi
    fi

    log_success "Monitoring setup validated"
}

# Main execution
main() {
    local phase="${1:-all}"

    log_info "Starting Golden Path Demo GitOps validation..."
    log_info "Phase: $phase"

    case "$phase" in
        "prerequisites")
            validate_prerequisites
            ;;
        "repositories")
            validate_prerequisites
            validate_github_repositories
            ;;
        "manifests")
            validate_prerequisites
            validate_kubernetes_manifests
            validate_argocd_applications
            ;;
        "deployment")
            validate_prerequisites
            validate_deployment_status
            ;;
        "application")
            validate_prerequisites
            validate_application_connectivity
            ;;
        "monitoring")
            validate_prerequisites
            validate_monitoring
            ;;
        "all")
            validate_prerequisites
            validate_github_repositories
            validate_kubernetes_manifests
            validate_argocd_applications
            validate_deployment_status
            validate_application_connectivity
            validate_monitoring
            ;;
        *)
            log_error "Unknown phase: $phase"
            log_info "Available phases: prerequisites, repositories, manifests, deployment, application, monitoring, all"
            exit 1
            ;;
    esac

    log_success "Validation completed successfully!"
}

# Run main function with all arguments
main "$@"