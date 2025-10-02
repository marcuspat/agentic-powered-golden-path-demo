# {{appName}} GitOps Configuration

This repository contains the GitOps manifests for deploying the {{appName}} application using ArgoCD.

## 📋 Manifests

- `deployment.yaml` - Kubernetes Deployment for the application
- `service.yaml` - Service to expose the application within the cluster
- `ingress.yaml` - Ingress to expose the application externally
- `configmap.yaml` - Configuration data for the application

## 🚀 Deployment

This repository is managed by ArgoCD. Changes will be automatically synchronized to the Kubernetes cluster.

### Manual Deployment (for testing)

```bash
# Apply all manifests
kubectl apply -f .

# Check deployment status
kubectl get deployment {{appName}}
kubectl get service {{appName}}
kubectl get pods -l app={{appName}}
```

## 🔧 Configuration

The following variables are automatically substituted:

- `{{appName}}` - Application name
- `{{description}}` - Application description
- `{{imageName}}` - Container image name
- `{{imageTag}}` - Container image tag
- `{{ingressHost}}` - External ingress host

## 📊 Monitoring

Check application status:

```bash
# View pods
kubectl get pods -l app={{appName}}

# View logs
kubectl logs -l app={{appName}} --follow

# View service
kubectl get service {{appName}}
```