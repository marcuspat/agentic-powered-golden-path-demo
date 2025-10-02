# GitOps Integration Workflow for Golden Path Demo

## Executive Summary

This document provides a comprehensive GitOps workflow integration for the Golden Path demo, leveraging the existing idpbuilder foundation with ArgoCD, GitHub repositories, and Kubernetes deployment patterns. The workflow follows a complete CI/CD pipeline from GitHub repository creation through automated deployment and monitoring.

## Architecture Overview

### Core Components

1. **GitHub Repositories** - Paired source and GitOps repositories
2. **idpbuilder** - Internal Development Platform with embedded ArgoCD
3. **ArgoCD** - GitOps operator for continuous deployment
4. **Kubernetes Cluster** - Target deployment environment
5. **NodeJS Application** - Sample application for demonstration

### Integration Flow

```
GitHub Push → CI Pipeline → Stack Update → ArgoCD Sync → K8s Deployment → Monitoring
     ↓              ↓            ↓             ↓              ↓
Source Repo → Build/Test → GitOps Repo → Application → Pod/Service
```

## Phase 1: Workflow Analysis

### 1.1 Complete GitOps Flow Mapping

#### Step 1: Repository Creation and Setup
**Action**: Create paired GitHub repositories
- **Source Repository**: Contains application code, CI/CD pipelines
- **GitOps Repository**: Contains Kubernetes manifests and ArgoCD applications

**Integration Points**:
- GitHub API for repository creation
- GitHub Actions for CI/CD automation
- Webhook configuration for automatic triggers

#### Step 2: Stack Population
**Action**: Populate GitOps repository with idpbuilder stack definitions
- Copy relevant stack templates from `/stacks/` directory
- Customize for NodeJS application requirements
- Configure parameter substitution and templating

**Integration Checkpoints**:
- Stack structure validation
- Manifest syntax verification
- Parameter substitution testing

#### Step 3: ArgoCD Application Creation
**Action**: Register ArgoCD applications pointing to GitOps repository
- Create Application resources targeting GitOps repo paths
- Configure sync policies and automated deployment
- Set up monitoring and health checks

**Integration Checkpoints**:
- ArgoCD application health status
- Repository connectivity validation
- Sync policy configuration verification

#### Step 4: Kubernetes Deployment
**Action**: Automated deployment through ArgoCD
- Monitor deployment progress and health
- Validate service availability and ingress configuration
- Verify application functionality

**Integration Checkpoints**:
- Pod health and readiness status
- Service endpoint accessibility
- Application response validation

### 1.2 Integration Validation Strategy

#### Pre-Deployment Validation
```bash
# Stack structure validation
find stacks/ -name "*.yaml" -exec kubeval {} \;

# Manifest syntax checking
kubectl apply --dry-run=client -f gitops-repo/

# ArgoCD application validation
argocd app validate --name golden-path-demo
```

#### Post-Deployment Validation
```bash
# Application health check
kubectl get pods -n golden-path-demo
kubectl get services -n golden-path-demo

# Service accessibility test
curl -k https://golden-path-demo.localtest.me/health

# ArgoCD sync status
argocd app get golden-path-demo
```

## Phase 2: Integration Implementation

### 2.1 GitHub Repository Structure

#### Source Repository: `golden-path-demo-source`
```
golden-path-demo-source/
├── .github/
│   └── workflows/
│       ├── ci.yml                 # CI pipeline
│       ├── update-gitops.yml      # GitOps update trigger
│       └── release.yml            # Release automation
├── src/
│   ├── app.js                     # NodeJS application
│   ├── package.json
│   └── Dockerfile
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   └── api.md
├── .gitignore
├── README.md
└── .version                       # Version tracking
```

#### GitOps Repository: `golden-path-demo-gitops`
```
golden-path-demo-gitops/
├── environments/
│   ├── dev/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   └── application.yaml       # ArgoCD Application
│   ├── staging/
│   └── prod/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
├── scripts/
│   ├── validate.sh
│   └── deploy.sh
└── README.md
```

### 2.2 Kubernetes Deployment Manifests

#### Namespace Configuration
```yaml
# environments/dev/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: golden-path-demo
  labels:
    environment: dev
    project: golden-path-demo
```

#### ConfigMap with Parameter Substitution
```yaml
# environments/dev/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: golden-path-demo-config
  namespace: golden-path-demo
data:
  APP_VERSION: "${APP_VERSION}"
  ENVIRONMENT: "dev"
  LOG_LEVEL: "info"
  API_PORT: "3000"
  DATABASE_URL: "${DATABASE_URL}"
  REDIS_URL: "${REDIS_URL}"
```

#### NodeJS Application Deployment
```yaml
# environments/dev/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: golden-path-demo
  namespace: golden-path-demo
  labels:
    app: golden-path-demo
    version: "${APP_VERSION}"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: golden-path-demo
  template:
    metadata:
      labels:
        app: golden-path-demo
        version: "${APP_VERSION}"
    spec:
      containers:
      - name: golden-path-demo
        image: "ghcr.io/your-org/golden-path-demo:${APP_VERSION}"
        ports:
        - containerPort: 3000
          name: http
        env:
        - name: NODE_ENV
          value: "dev"
        - name: PORT
          valueFrom:
            configMapKeyRef:
              name: golden-path-demo-config
              key: API_PORT
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: golden-path-demo-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: golden-path-demo-secrets
              key: redis-url
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### Service Configuration
```yaml
# environments/dev/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: golden-path-demo-service
  namespace: golden-path-demo
  labels:
    app: golden-path-demo
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 3000
    protocol: TCP
    name: http
  selector:
    app: golden-path-demo
```

#### Ingress Configuration
```yaml
# environments/dev/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: golden-path-demo-ingress
  namespace: golden-path-demo
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - golden-path-demo.localtest.me
    secretName: golden-path-demo-tls
  rules:
  - host: golden-path-demo.localtest.me
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: golden-path-demo-service
            port:
              number: 80
```

### 2.3 ArgoCD Application Configuration

#### Main Application Manifest
```yaml
# environments/dev/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: golden-path-demo-dev
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
  labels:
    environment: dev
    project: golden-path-demo
spec:
  project: default
  sources:
    # Primary source: GitOps repository
    - repoURL: https://github.com/your-org/golden-path-demo-gitops.git
      targetRevision: main
      path: environments/dev
      ref: values
    # Values file from source repository
    - repoURL: https://github.com/your-org/golden-path-demo-source.git
      targetRevision: main
      path: .version
  destination:
    server: https://kubernetes.default.svc
    namespace: golden-path-demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
      - PruneLast=true
      - RespectIgnoreDifferences=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
  revisionHistoryLimit: 10
  ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers:
    - /spec/replicas
```

#### ApplicationSet for Multi-Environment
```yaml
# applicationset.yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: golden-path-demo-set
  namespace: argocd
spec:
  generators:
  - git:
      repoURL: https://github.com/your-org/golden-path-demo-gitops.git
      revision: HEAD
      directories:
      - path: environments/*
  template:
    metadata:
      name: 'golden-path-demo-{{path.basename}}'
      namespace: argocd
    spec:
      project: default
      source:
        repoURL: https://github.com/your-org/golden-path-demo-gitops.git
        targetRevision: HEAD
        path: '{{path}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: 'golden-path-demo-{{path.basename}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
        - CreateNamespace=true
```

## Phase 3: Validation Strategy

### 3.1 Verification Commands by Phase

#### Phase 1: Repository Setup Validation
```bash
# Verify repository creation and structure
gh repo view your-org/golden-path-demo-source
gh repo view your-org/golden-path-demo-gitops

# Validate webhook configuration
gh api repos/your-org/golden-path-demo-source/hooks

# Check CI/CD workflow status
gh workflow list --repo your-org/golden-path-demo-source
```

#### Phase 2: Stack Population Validation
```bash
# Validate stack structure
tree golden-path-demo-gitops/environments/

# Verify manifest syntax
kubectl apply --dry-run=client -f golden-path-demo-gitops/environments/dev/

# Check parameter substitution
envsubst < golden-path-demo-gitops/environments/dev/deployment.yaml | kubectl apply --dry-run=client -f -
```

#### Phase 3: ArgoCD Integration Validation
```bash
# Verify ArgoCD server connectivity
argocd account get-user-info

# Validate application configuration
argocd app validate --file golden-path-demo-gitops/environments/dev/application.yaml

# Check repository access
argocd repo list
```

#### Phase 4: Deployment Validation
```bash
# Monitor deployment progress
kubectl get pods -n golden-path-demo -w

# Check service availability
kubectl get services -n golden-path-demo

# Verify ingress configuration
kubectl get ingress -n golden-path-demo

# Test application endpoint
curl -k https://golden-path-demo.localtest.me/health
```

### 3.2 Rollback Procedures

#### Application Rollback
```bash
# Rollback to previous revision
argocd app rollback golden-path-demo-dev --revision <previous-revision>

# Sync to specific Git commit
argocd app sync golden-path-demo-dev --revision <commit-hash>

# Disable automated sync
argocd app set golden-path-demo-dev --sync-policy none
```

#### Environment Recovery
```bash
# Delete namespace and recreate
kubectl delete namespace golden-path-demo
kubectl apply -f golden-path-demo-gitops/environments/dev/namespace.yaml

# Restore from backup
kubectl apply -f backups/golden-path-demo-<timestamp>.yaml
```

#### GitOps Repository Recovery
```bash
# Reset to working commit
cd golden-path-demo-gitops
git reset --hard <working-commit>

# Force push to restore state
git push --force-with-lease origin main
```

### 3.3 Monitoring and Observability

#### ArgoCD Monitoring
```bash
# Application health status
argocd app get golden-path-demo-dev --hard-refresh

# Sync history
argocd app history golden-path-demo-dev

# Resource status
argocd app resources golden-path-demo-dev
```

#### Kubernetes Monitoring
```bash
# Pod metrics
kubectl top pods -n golden-path-demo

# Service metrics
kubectl get endpointslices -n golden-path-demo

# Ingress metrics
kubectl ingress -n golden-path-demo
```

#### Application Monitoring
```bash
# Health check endpoint
curl -f https://golden-path-demo.localtest.me/health

# Metrics endpoint
curl https://golden-path-demo.localtest.me/metrics

# Log aggregation
kubectl logs -n golden-path-demo -l app=golden-path-demo --tail=100
```

## Success Metrics

### Deployment Success Criteria
- [ ] ArgoCD application status: Healthy
- [ ] All pods running and ready
- [ ] Service endpoints accessible
- [ ] Ingress configuration functional
- [ ] Application health checks passing
- [ ] Automated sync working correctly

### Performance Metrics
- [ ] Deployment time < 5 minutes
- [ ] Health check response time < 200ms
- [ ] Pod restart rate < 1%
- [ ] Resource utilization within limits
- [ ] Error rate < 0.1%

### Integration Validation
- [ ] Git push triggers automatic deployment
- [ ] Rollback procedures functional
- [ ] Monitoring alerts configured
- [ ] Backup and recovery verified
- [ ] Documentation complete and accurate

## Step-by-Step Commands

### Initial Setup
```bash
# 1. Create GitHub repositories
gh repo create your-org/golden-path-demo-source --public --clone
gh repo create your-org/golden-path-demo-gitops --public --clone

# 2. Setup source repository
cd golden-path-demo-source
mkdir -p .github/workflows src tests docs
# Add application code and CI/CD configuration
git add .
git commit -m "Initial application setup"
git push origin main

# 3. Setup GitOps repository
cd ../golden-path-demo-gitops
mkdir -p environments/{dev,staging,prod} base scripts
# Copy and customize manifests from this document
git add .
git commit -m "Initial GitOps configuration"
git push origin main

# 4. Configure webhooks and secrets
gh secret set GH_TOKEN --repo your-org/golden-path-demo-source --body "$GH_TOKEN"
gh api repos/your-org/golden-path-demo-source/hooks -X POST -H "Authorization: token $GH_TOKEN" --data '{"name":"web","active":true,"events":["push"],"config":{"url":"https://your-ci-server.com/webhook"}}'
```

### idpbuilder Integration
```bash
# 5. Start idpbuilder with ArgoCD
./idpbuilder create

# 6. Port-forward to access ArgoCD
kubectl port-forward svc/argocd-server -n argocd 8080:443

# 7. Login to ArgoCD
argocd login localhost:8080 --username admin --password $(kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d)

# 8. Register GitOps repository in ArgoCD
argocd repo add https://github.com/your-org/golden-path-demo-gitops.git --username github --password $GH_TOKEN

# 9. Create ArgoCD application
kubectl apply -f golden-path-demo-gitops/environments/dev/application.yaml
```

### Deployment Verification
```bash
# 10. Monitor deployment
argocd app get golden-path-demo-dev --refresh
watch kubectl get pods -n golden-path-demo

# 11. Verify service accessibility
kubectl get svc -n golden-path-demo
kubectl get ingress -n golden-path-demo

# 12. Test application
curl -k https://golden-path-demo.localtest.me/health
curl -k https://golden-path-demo.localtest.me/api/version
```

This comprehensive GitOps integration workflow provides a complete, production-ready implementation for the Golden Path demo, leveraging the existing idpbuilder foundation while following best practices for GitOps workflows, monitoring, and validation.