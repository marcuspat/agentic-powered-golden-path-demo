#!/bin/bash

# Golden Path Demo GitOps Rollback Script
# This script provides rollback procedures for different scenarios

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GITHUB_ORG="${GITHUB_ORG:-your-org}"
SOURCE_REPO="${SOURCE_REPO:-golden-path-demo-source}"
GITOPS_REPO="${GITOPS_REPO:-golden-path-demo-gitops}"
NAMESPACE="${NAMESPACE:-golden-path-demo}"
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"

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

# Backup functions
create_backup() {
    local backup_name="golden-path-demo-backup-$(date +%Y%m%d-%H%M%S)"
    local backup_path="$BACKUP_DIR/$backup_name"

    log_info "Creating backup: $backup_name"

    mkdir -p "$backup_path"

    # Backup Kubernetes resources
    log_info "Backing up Kubernetes resources..."
    kubectl get namespace "$NAMESPACE" -o yaml > "$backup_path/namespace.yaml" 2>/dev/null || true
    kubectl get all -n "$NAMESPACE" -o yaml > "$backup_path/all-resources.yaml" 2>/dev/null || true
    kubectl get secrets -n "$NAMESPACE" -o yaml > "$backup_path/secrets.yaml" 2>/dev/null || true
    kubectl get configmaps -n "$NAMESPACE" -o yaml > "$backup_path/configmaps.yaml" 2>/dev/null || true

    # Backup ArgoCD application
    log_info "Backing up ArgoCD application..."
    kubectl get application golden-path-demo-dev -n "$ARGOCD_NAMESPACE" -o yaml > "$backup_path/argocd-application.yaml" 2>/dev/null || true

    # Backup GitOps repository state
    log_info "Backing up GitOps repository state..."
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" RETURN

    if gh repo clone "$GITHUB_ORG/$GITOPS_REPO" "$temp_dir/gitops" &> /dev/null; then
        cd "$temp_dir/gitops"
        git log --oneline -10 > "$backup_path/gitops-commit-history.txt"
        git archive HEAD -o "$backup_path/gitops-repo.tar"
    fi

    # Backup source repository state
    log_info "Backing up source repository state..."
    if gh repo clone "$GITHUB_ORG/$SOURCE_REPO" "$temp_dir/source" &> /dev/null; then
        cd "$temp_dir/source"
        git log --oneline -10 > "$backup_path/source-commit-history.txt"
        git archive HEAD -o "$backup_path/source-repo.tar"
    fi

    # Create backup metadata
    cat > "$backup_path/backup-metadata.txt" << EOF
Backup created: $(date)
Namespace: $NAMESPACE
Source Repository: $GITHUB_ORG/$SOURCE_REPO
GitOps Repository: $GITHUB_ORG/$GITOPS_REPO
ArgoCD Application: golden-path-demo-dev
ArgoCD Namespace: $ARGOCD_NAMESPACE

Current GitOps commit: $(cd "$temp_dir/gitops" 2>/dev/null && git rev-parse HEAD || echo "unknown")
Current Source commit: $(cd "$temp_dir/source" 2>/dev/null && git rev-parse HEAD || echo "unknown")
EOF

    log_success "Backup created: $backup_path"
    echo "$backup_path"
}

# Rollback functions
rollback_application() {
    local target_revision="${1:-HEAD~1}"

    log_info "Rolling back application to revision: $target_revision"

    # Method 1: Rollback ArgoCD application
    if argocd app get golden-path-demo-dev &> /dev/null; then
        log_info "Rolling back ArgoCD application..."
        argocd app rollback golden-path-demo-dev --revision "$target_revision"

        # Wait for rollback to complete
        log_info "Waiting for rollback to complete..."
        argocd app wait golden-path-demo-dev --timeout 300
        log_success "ArgoCD application rolled back successfully"
    else
        log_error "ArgoCD application not found"
        return 1
    fi
}

rollback_gitops_repo() {
    local target_commit="${1:-HEAD~1}"

    log_info "Rolling back GitOps repository to commit: $target_commit"

    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" RETURN

    # Clone GitOps repository
    if gh repo clone "$GITHUB_ORG/$GITOPS_REPO" "$temp_dir/gitops" &> /dev/null; then
        cd "$temp_dir/gitops"

        # Reset to target commit
        git reset --hard "$target_commit"

        # Force push to rollback
        git push --force-with-lease origin main

        log_success "GitOps repository rolled back successfully"

        # Trigger ArgoCD sync
        log_info "Triggering ArgoCD sync..."
        argocd app sync golden-path-demo-dev
    else
        log_error "Failed to clone GitOps repository"
        return 1
    fi
}

rollback_source_repo() {
    local target_commit="${1:-HEAD~1}"

    log_info "Rolling back source repository to commit: $target_commit"

    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" RETURN

    # Clone source repository
    if gh repo clone "$GITHUB_ORG/$SOURCE_REPO" "$temp_dir/source" &> /dev/null; then
        cd "$temp_dir/source"

        # Reset to target commit
        git reset --hard "$target_commit"

        # Force push to rollback
        git push --force-with-lease origin main

        log_success "Source repository rolled back successfully"
    else
        log_error "Failed to clone source repository"
        return 1
    fi
}

rollback_kubernetes_resources() {
    local backup_path="${1:-}"

    if [[ -z "$backup_path" ]]; then
        log_error "Backup path required for Kubernetes resource rollback"
        return 1
    fi

    if [[ ! -d "$backup_path" ]]; then
        log_error "Backup directory not found: $backup_path"
        return 1
    fi

    log_info "Rolling back Kubernetes resources from backup: $backup_path"

    # Delete existing namespace
    log_info "Deleting existing namespace..."
    kubectl delete namespace "$NAMESPACE" --ignore-not-found=true

    # Wait for namespace to be fully deleted
    log_info "Waiting for namespace deletion to complete..."
    kubectl wait --for=delete namespace "$NAMESPACE" --timeout=300 || true

    # Restore namespace
    if [[ -f "$backup_path/namespace.yaml" ]]; then
        log_info "Restoring namespace..."
        kubectl apply -f "$backup_path/namespace.yaml"
    fi

    # Restore secrets
    if [[ -f "$backup_path/secrets.yaml" ]]; then
        log_info "Restoring secrets..."
        kubectl apply -f "$backup_path/secrets.yaml"
    fi

    # Restore configmaps
    if [[ -f "$backup_path/configmaps.yaml" ]]; then
        log_info "Restoring configmaps..."
        kubectl apply -f "$backup_path/configmaps.yaml"
    fi

    # Restore all resources
    if [[ -f "$backup_path/all-resources.yaml" ]]; then
        log_info "Restoring all resources..."
        kubectl apply -f "$backup_path/all-resources.yaml"
    fi

    # Restore ArgoCD application
    if [[ -f "$backup_path/argocd-application.yaml" ]]; then
        log_info "Restoring ArgoCD application..."
        kubectl apply -f "$backup_path/argocd-application.yaml"
    fi

    log_success "Kubernetes resources rolled back successfully"
}

disable_argocd_sync() {
    log_info "Disabling ArgoCD automated sync..."

    if argocd app get golden-path-demo-dev &> /dev/null; then
        argocd app set golden-path-demo-dev --sync-policy none
        log_success "ArgoCD automated sync disabled"
    else
        log_warning "ArgoCD application not found"
    fi
}

enable_argocd_sync() {
    log_info "Enabling ArgoCD automated sync..."

    if argocd app get golden-path-demo-dev &> /dev/null; then
        argocd app set golden-path-demo-dev --sync-policy automated --auto-prune --self-heal
        log_success "ArgoCD automated sync enabled"
    else
        log_warning "ArgoCD application not found"
    fi
}

list_backups() {
    log_info "Available backups:"

    if [[ -d "$BACKUP_DIR" ]]; then
        local backups=($(ls -t "$BACKUP_DIR" 2>/dev/null | grep "golden-path-demo-backup-" || true))

        if [[ ${#backups[@]} -eq 0 ]]; then
            log_info "No backups found"
        else
            for backup in "${backups[@]}"; do
                local backup_path="$BACKUP_DIR/$backup"
                if [[ -f "$backup_path/backup-metadata.txt" ]]; then
                    echo "  📦 $backup ($(head -1 "$backup_path/backup-metadata.txt" | cut -d' ' -f3-))"
                else
                    echo "  📦 $backup"
                fi
            done
        fi
    else
        log_info "Backup directory does not exist: $BACKUP_DIR"
    fi
}

show_status() {
    log_info "Current system status:"

    # Namespace status
    if kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_success "✓ Namespace $NAMESPACE exists"
    else
        log_warning "✗ Namespace $NAMESPACE does not exist"
    fi

    # ArgoCD application status
    if argocd app get golden-path-demo-dev &> /dev/null; then
        local status=$(argocd app get golden-path-demo-dev -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
        local sync_status=$(argocd app get golden-path-demo-dev -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")
        log_success "✓ ArgoCD application exists (Health: $status, Sync: $sync_status)"
    else
        log_warning "✗ ArgoCD application does not exist"
    fi

    # Pod status
    local pod_count=$(kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | wc -l || echo "0")
    if [[ $pod_count -gt 0 ]]; then
        log_success "✓ $pod_count pods found in namespace $NAMESPACE"
    else
        log_warning "✗ No pods found in namespace $NAMESPACE"
    fi

    # Repository status
    if gh repo view "$GITHUB_ORG/$SOURCE_REPO" &> /dev/null; then
        log_success "✓ Source repository exists"
    else
        log_warning "✗ Source repository does not exist"
    fi

    if gh repo view "$GITHUB_ORG/$GITOPS_REPO" &> /dev/null; then
        log_success "✓ GitOps repository exists"
    else
        log_warning "✗ GitOps repository does not exist"
    fi
}

# Emergency rollback (complete reset)
emergency_rollback() {
    local backup_path="${1:-}"

    log_warning "🚨 EMERGENCY ROLLBACK INITIATED 🚨"
    log_warning "This will completely reset the application to a known good state"

    # Create emergency backup before proceeding
    local emergency_backup=$(create_backup)
    log_info "Emergency backup created: $emergency_backup"

    # Disable ArgoCD sync first
    disable_argocd_sync

    # Rollback Kubernetes resources if backup provided
    if [[ -n "$backup_path" ]]; then
        rollback_kubernetes_resources "$backup_path"
    else
        log_warning "No backup path provided, only ArgoCD sync will be disabled"
        log_warning "You will need to manually restore resources"
    fi

    log_warning "Emergency rollback completed. Review system status and re-enable sync when ready."
}

# Help function
show_help() {
    cat << EOF
Golden Path Demo GitOps Rollback Script

Usage: $0 <command> [options]

Commands:
    backup                                   Create a backup of current state
    rollback-app [revision]                  Rollback application to specific revision
    rollback-gitops [commit]                 Rollback GitOps repository to specific commit
    rollback-source [commit]                 Rollback source repository to specific commit
    rollback-k8s [backup-path]               Rollback Kubernetes resources from backup
    disable-sync                             Disable ArgoCD automated sync
    enable-sync                              Enable ArgoCD automated sync
    list-backups                             List available backups
    status                                   Show current system status
    emergency-rollback [backup-path]         Emergency rollback with complete reset
    help                                     Show this help message

Examples:
    $0 backup                                                    # Create backup
    $0 rollback-app HEAD~1                                       # Rollback to previous revision
    $0 rollback-gitops abc123                                    # Rollback GitOps to specific commit
    $0 rollback-k8s /path/to/backup                             # Restore from backup
    $0 emergency-rollback /path/to/backup                       # Emergency rollback

Environment Variables:
    GITHUB_ORG           GitHub organization name (default: your-org)
    SOURCE_REPO          Source repository name (default: golden-path-demo-source)
    GITOPS_REPO          GitOps repository name (default: golden-path-demo-gitops)
    NAMESPACE            Kubernetes namespace (default: golden-path-demo)
    ARGOCD_NAMESPACE     ArgoCD namespace (default: argocd)
    BACKUP_DIR           Backup directory (default: ./backups)

EOF
}

# Main execution
main() {
    local command="${1:-help}"

    case "$command" in
        "backup")
            create_backup
            ;;
        "rollback-app")
            rollback_application "${2:-HEAD~1}"
            ;;
        "rollback-gitops")
            rollback_gitops_repo "${2:-HEAD~1}"
            ;;
        "rollback-source")
            rollback_source_repo "${2:-HEAD~1}"
            ;;
        "rollback-k8s")
            rollback_kubernetes_resources "${2:-}"
            ;;
        "disable-sync")
            disable_argocd_sync
            ;;
        "enable-sync")
            enable_argocd_sync
            ;;
        "list-backups")
            list_backups
            ;;
        "status")
            show_status
            ;;
        "emergency-rollback")
            emergency_rollback "${2:-}"
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"