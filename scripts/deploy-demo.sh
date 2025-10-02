#!/bin/bash

# Golden Path Demo Deployment Script
# Complete end-to-end deployment with validation and monitoring

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GITHUB_ORG="${GITHUB_ORG:-your-org}"
SOURCE_REPO="${SOURCE_REPO:-golden-path-demo-source}"
GITOPS_REPO="${GITOPS_REPO:-golden-path-demo-gitops}"
NAMESPACE="${NAMESPACE:-golden-path-demo}"
ARGOCD_NAMESPACE="${ARGOCD_NAMESPACE:-argocd}"
DOMAIN="${DOMAIN:-localtest.me}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# Progress tracking
STEP=1
TOTAL_STEPS=8

progress() {
    local message="$1"
    echo -e "\n${PURPLE}=== [${STEP}/${TOTAL_STEPS}] $message ===${NC}\n"
    ((STEP++))
}

# Validation functions
validate_prerequisites() {
    progress "Validating prerequisites"

    # Check required tools
    local tools=("gh" "kubectl" "argocd" "helm" "kustomize")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "Required tool '$tool' is not installed"
            return 1
        fi
    done

    # Check authentication
    if ! gh auth status &> /dev/null; then
        log_error "GitHub CLI is not authenticated"
        return 1
    fi

    # Check cluster access
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot access Kubernetes cluster"
        return 1
    fi

    log_success "Prerequisites validated"
}

setup_repositories() {
    progress "Setting up GitHub repositories"

    # Create source repository if it doesn't exist
    if ! gh repo view "$GITHUB_ORG/$SOURCE_REPO" &> /dev/null; then
        log_info "Creating source repository: $GITHUB_ORG/$SOURCE_REPO"
        gh repo create "$GITHUB_ORG/$SOURCE_REPO" --public --clone
        cd "$SOURCE_REPO"

        # Create basic structure
        mkdir -p src tests .github/workflows docs

        # Create sample application
        cat > src/package.json << EOF
{
  "name": "golden-path-demo",
  "version": "1.0.0",
  "description": "Golden Path Demo Application",
  "main": "app.js",
  "scripts": {
    "start": "node app.js",
    "test": "jest"
  },
  "dependencies": {
    "express": "^4.18.0",
    "prom-client": "^14.0.0",
    "winston": "^3.8.0"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "supertest": "^6.2.0"
  }
}
EOF

        cat > src/app.js << EOF
const express = require('express');
const promClient = require('prom-client');
const winston = require('winston');

const app = express();
const PORT = process.env.PORT || 3000;

// Prometheus metrics
const register = new promClient.Registry();
promClient.collectDefaultMetrics({ register });

const httpRequestDuration = new promClient.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.1, 0.3, 0.5, 0.7, 1, 3, 5, 7, 10]
});

const httpRequestTotal = new promClient.Counter({
  name: 'http_requests_total',
  help: 'Total number of HTTP requests',
  labelNames: ['method', 'route', 'status_code']
});

register.registerMetric(httpRequestDuration);
register.registerMetric(httpRequestTotal);

// Winston logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console()
  ]
});

// Middleware
app.use(express.json());
app.use((req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = (Date.now() - start) / 1000;
    httpRequestDuration
      .labels(req.method, req.route?.path || req.path, res.statusCode)
      .observe(duration);
    httpRequestTotal
      .labels(req.method, req.route?.path || req.path, res.statusCode)
      .inc();
  });
  next();
});

// Routes
app.get('/health', (req, res) => {
  logger.info('Health check requested');
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

app.get('/ready', (req, res) => {
  res.json({ status: 'ready', timestamp: new Date().toISOString() });
});

app.get('/api/version', (req, res) => {
  res.json({
    version: process.env.APP_VERSION || '1.0.0',
    name: 'golden-path-demo',
    environment: process.env.NODE_ENV || 'development'
  });
});

app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.end(await register.metrics());
});

// Start server
app.listen(PORT, () => {
  logger.info(\`Golden Path Demo listening on port \${PORT}\`);
});

module.exports = app;
EOF

        cat > src/Dockerfile << EOF
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY . .

EXPOSE 3000

USER node

CMD ["npm", "start"]
EOF

        # Create CI/CD workflow
        mkdir -p .github/workflows
        cat > .github/workflows/ci.yml << EOF
name: CI/CD Pipeline

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
        cache: 'npm'
        cache-dependency-path: src/package-lock.json

    - name: Install dependencies
      run: |
        cd src
        npm ci

    - name: Run tests
      run: |
        cd src
        npm test

    - name: Build Docker image
      run: |
        docker build -t ghcr.io/\${{ github.repository_owner }}/\${{ github.event.repository.name }}:\${{ github.sha }} src/

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
    - uses: actions/checkout@v3

    - name: Update GitOps repository
      run: |
        echo "Triggering GitOps update..."
        # This would typically update the GitOps repo with new image tag
EOF

        git add .
        git commit -m "Initial application setup"
        git push origin main
        cd ..
    else
        log_success "Source repository already exists"
    fi

    # Create GitOps repository if it doesn't exist
    if ! gh repo view "$GITHUB_ORG/$GITOPS_REPO" &> /dev/null; then
        log_info "Creating GitOps repository: $GITHUB_ORG/$GITOPS_REPO"
        gh repo create "$GITHUB_ORG/$GITOPS_REPO" --public --clone
        cd "$GITOPS_REPO"

        # Copy our configuration files
        cp -r "$PROJECT_ROOT/config" .
        cp -r "$PROJECT_ROOT/scripts" .

        # Create README
        cat > README.md << EOF
# Golden Path Demo GitOps Repository

This repository contains the GitOps configuration for the Golden Path demo application.

## Structure

- \`config/kubernetes/\` - Kubernetes manifests
- \`config/argocd/\` - ArgoCD application definitions
- \`config/monitoring/\` - Monitoring and observability configs
- \`scripts/\` - Utility scripts for deployment and validation

## Deployment

The ArgoCD application will automatically sync changes from this repository.
EOF

        git add .
        git commit -m "Initial GitOps configuration"
        git push origin main
        cd ..
    else
        log_success "GitOps repository already exists"
    fi

    log_success "Repositories setup completed"
}

deploy_kubernetes_resources() {
    progress "Deploying Kubernetes resources"

    # Create namespace
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/namespace.yaml"

    # Deploy application resources
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/configmap.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/secrets.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/serviceaccount.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/deployment.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/service.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/ingress.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/hpa.yaml"
    kubectl apply -f "$PROJECT_ROOT/config/kubernetes/networkpolicy.yaml"

    log_success "Kubernetes resources deployed"
}

setup_argocd() {
    progress "Setting up ArgoCD"

    # Check if ArgoCD is installed
    if ! kubectl get namespace "$ARGOCD_NAMESPACE" &> /dev/null; then
        log_info "Installing ArgoCD..."
        kubectl create namespace "$ARGOCD_NAMESPACE"
        kubectl apply -n "$ARGOCD_NAMESPACE" -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

        # Wait for ArgoCD to be ready
        kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server -n "$ARGOCD_NAMESPACE" --timeout=300s
    fi

    # Create ArgoCD project
    kubectl apply -f "$PROJECT_ROOT/config/argocd/project.yaml"

    # Add GitOps repository to ArgoCD
    local gitops_url="https://github.com/$GITHUB_ORG/$GITOPS_REPO.git"
    argocd repo add "$gitops_url" --username github --password "$GH_TOKEN" || log_warning "Repository might already exist"

    # Create ArgoCD application
    kubectl apply -f "$PROJECT_ROOT/config/argocd/application.yaml"

    log_success "ArgoCD setup completed"
}

setup_monitoring() {
    progress "Setting up monitoring"

    # Deploy ServiceMonitor
    kubectl apply -f "$PROJECT_ROOT/config/monitoring/prometheus-servicemonitor.yaml"

    # Deploy PrometheusRule
    kubectl apply -f "$PROJECT_ROOT/config/monitoring/prometheusrule.yaml"

    # Note: In a real environment, you would also set up Prometheus, Grafana, and AlertManager
    # This is simplified for the demo

    log_success "Monitoring setup completed"
}

validate_deployment() {
    progress "Validating deployment"

    # Run validation script
    if "$PROJECT_ROOT/scripts/validate.sh" deployment; then
        log_success "Deployment validation passed"
    else
        log_error "Deployment validation failed"
        return 1
    fi

    # Additional manual validation
    log_info "Waiting for deployment to be ready..."
    kubectl wait --for=condition=available deployment/golden-path-demo -n "$NAMESPACE" --timeout=300s

    # Check pod status
    local pods=$(kubectl get pods -n "$NAMESPACE" -l app=golden-path-demo --no-headers | wc -l)
    log_info "Number of pods: $pods"

    # Check service status
    kubectl get svc -n "$NAMESPACE"

    # Check ingress status
    kubectl get ingress -n "$NAMESPACE"

    log_success "Deployment validation completed"
}

test_connectivity() {
    progress "Testing application connectivity"

    # Get ingress hostname
    local ingress_host=$(kubectl get ingress golden-path-demo-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")

    if [[ -z "$ingress_host" ]]; then
        log_error "Could not determine ingress hostname"
        return 1
    fi

    log_info "Testing connectivity to https://$ingress_host"

    # Wait for DNS resolution
    log_info "Waiting for DNS resolution..."
    local retries=0
    while ! nslookup "$ingress_host" &> /dev/null && [[ $retries -lt 30 ]]; do
        sleep 10
        ((retries++))
    done

    # Test endpoints
    local endpoints=("/health" "/ready" "/api/version")
    for endpoint in "${endpoints[@]}"; do
        log_info "Testing $endpoint..."
        if curl -f -s -k "https://$ingress_host$endpoint" &> /dev/null; then
            log_success "✓ $endpoint is responding"
        else
            log_warning "✗ $endpoint is not responding"
        fi
    done

    log_success "Connectivity testing completed"
}

create_backup() {
    progress "Creating initial backup"

    local backup_dir="$PROJECT_ROOT/backups/initial-deployment-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"

    # Backup current state
    kubectl get all -n "$NAMESPACE" -o yaml > "$backup_dir/all-resources.yaml"
    kubectl get secrets -n "$NAMESPACE" -o yaml > "$backup_dir/secrets.yaml"
    kubectl get configmaps -n "$NAMESPACE" -o yaml > "$backup_dir/configmaps.yaml"

    log_success "Initial backup created: $backup_dir"
}

show_summary() {
    progress "Deployment Summary"

    echo -e "\n${GREEN}🎉 Golden Path Demo deployment completed successfully!${NC}\n"

    echo -e "${BLUE}Access Information:${NC}"

    local ingress_host=$(kubectl get ingress golden-path-demo-ingress -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "unknown")
    echo -e "  • Application URL: ${YELLOW}https://$ingress_host${NC}"
    echo -e "  • Health Endpoint: ${YELLOW}https://$ingress_host/health${NC}"
    echo -e "  • API Version: ${YELLOW}https://$ingress_host/api/version${NC}"
    echo -e "  • Metrics: ${YELLOW}https://$ingress_host/metrics${NC}"

    echo -e "\n${BLUE}ArgoCD Information:${NC}"
    echo -e "  • ArgoCD URL: ${YELLOW}https://argocd.$DOMAIN${NC}"
    echo -e "  • Get ArgoCD password: ${YELLOW}kubectl -n $ARGOCD_NAMESPACE get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d${NC}"
    echo -e "  • Port-forward: ${YELLOW}kubectl port-forward svc/argocd-server -n $ARGOCD_NAMESPACE 8080:443${NC}"

    echo -e "\n${BLUE}Useful Commands:${NC}"
    echo -e "  • Check deployment status: ${YELLOW}kubectl get pods -n $NAMESPACE${NC}"
    echo -e "  • Check services: ${YELLOW}kubectl get svc -n $NAMESPACE${NC}"
    echo -e "  • Check ingress: ${YELLOW}kubectl get ingress -n $NAMESPACE${NC}"
    echo -e "  • View logs: ${YELLOW}kubectl logs -n $NAMESPACE -l app=golden-path-demo --tail=100${NC}"
    echo -e "  • Validate deployment: ${YELLOW}$PROJECT_ROOT/scripts/validate.sh${NC}"
    echo -e "  • Rollback deployment: ${YELLOW}$PROJECT_ROOT/scripts/rollback.sh rollback-app${NC}"

    echo -e "\n${BLUE}Next Steps:${NC}"
    echo -e "  1. Access the application via the URL above"
    echo -e "  2. Check ArgoCD dashboard for deployment status"
    echo -e "  3. Test the GitOps workflow by making changes"
    echo -e "  4. Review monitoring dashboards (if configured)"
    echo -e "  5. Test rollback procedures"

    echo -e "\n${GREEN}Happy GitOps! 🚀${NC}\n"
}

# Main execution
main() {
    local start_time=$(date +%s)

    echo -e "${PURPLE}"
    echo "============================================================"
    echo "    Golden Path Demo GitOps Deployment Script"
    echo "============================================================"
    echo -e "${NC}\n"

    validate_prerequisites
    setup_repositories
    deploy_kubernetes_resources
    setup_argocd
    setup_monitoring
    validate_deployment
    test_connectivity
    create_backup
    show_summary

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    local minutes=$((duration / 60))
    local seconds=$((duration % 60))

    echo -e "${GREEN}✅ Total deployment time: ${minutes}m ${seconds}s${NC}"
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 1' INT TERM

# Run main function
main "$@"