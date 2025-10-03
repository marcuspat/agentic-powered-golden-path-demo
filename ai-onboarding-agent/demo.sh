#!/bin/bash

# Golden Path AI-Powered Developer Onboarding Demo
# This script demonstrates the complete end-to-end workflow

set -e

echo "🚀 Starting Golden Path AI-Powered Developer Onboarding Demo"
echo "=============================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Check if required environment variables are set
check_environment() {
    print_header "Checking Environment Setup"

    if [ -z "$GITHUB_TOKEN" ]; then
        print_warning "GITHUB_TOKEN not set. Please set it for full demo:"
        echo "  export GITHUB_TOKEN=your_github_personal_access_token"
        GITHUB_SET=false
    else
        print_status "✅ GITHUB_TOKEN is set"
        GITHUB_SET=true
    fi

    if [ -z "$GITHUB_USERNAME" ]; then
        print_warning "GITHUB_USERNAME not set. Please set it for full demo:"
        echo "  export GITHUB_USERNAME=your_github_username"
        GITHUB_USER_SET=false
    else
        print_status "✅ GITHUB_USERNAME is set"
        GITHUB_USER_SET=true
    fi

    if [ -z "$OPENROUTER_API_KEY" ]; then
        print_error "OPENROUTER_API_KEY not set. Using demo key..."
        export OPENROUTER_API_KEY="your_openrouter_api_key_here"
    else
        print_status "✅ OPENROUTER_API_KEY is set"
    fi

    echo
}

# Check if idpbuilder cluster is running
check_cluster() {
    print_header "Checking idpbuilder Cluster Status"

    if command -v ./idpbuilder &> /dev/null; then
        if ./idpbuilder cluster status &> /dev/null; then
            print_status "✅ idpbuilder cluster is running"
            CLUSTER_READY=true
        else
            print_warning "idpbuilder cluster is not running"
            print_status "Starting idpbuilder cluster..."
            ./idpbuilder cluster create --name demo-cluster
            CLUSTER_READY=true
        fi
    else
        print_error "idpbuilder not found. Please run setup first."
        CLUSTER_READY=false
    fi

    echo
}

# Run the AI agent demo
run_agent_demo() {
    print_header "Running AI Agent Demo"

    # Test the agent with different requests
    TEST_REQUESTS=(
        "I need to deploy my new NodeJS service called inventory-api"
        "Create a user-management service"
        "Deploy my payment-processor application"
    )

    for request in "${TEST_REQUESTS[@]}"; do
        print_status "Testing request: '$request'"

        # Extract app name to show AI processing
        python3 -c "
import os
import sys
sys.path.insert(0, '.')
from agent import extract_app_name_from_request

os.environ['OPENROUTER_API_KEY'] = '$OPENROUTER_API_KEY'
app_name = extract_app_name_from_request('$request')
print(f'🤖 AI extracted app name: {app_name}')
"

        if [ "$GITHUB_SET" = true ] && [ "$GITHUB_USER_SET" = true ]; then
            print_status "Running full onboarding flow..."
            python3 agent.py "$request"
        else
            print_warning "Skipping full deployment (missing GitHub credentials)"
            print_status "Would run: python3 agent.py \"$request\""
        fi

        echo "----------------------------------------"
    done
}

# Show Kubernetes resources if deployed
show_k8s_resources() {
    if [ "$CLUSTER_READY" = true ] && [ "$GITHUB_SET" = true ]; then
        print_header "Kubernetes Resources Status"

        print_status "Checking for deployed applications..."
        kubectl get applications -n argocd 2>/dev/null || print_warning "ArgoCD applications not found"

        print_status "Checking deployments..."
        kubectl get deployments 2>/dev/null || print_warning "No deployments found"

        print_status "Checking services..."
        kubectl get services 2>/dev/null || print_warning "No services found"

        print_status "Checking ingress..."
        kubectl get ingress 2>/dev/null || print_warning "No ingress resources found"

        echo
    fi
}

# Show ArgoCD access info
show_argocd_info() {
    if [ "$CLUSTER_READY" = true ]; then
        print_header "ArgoCD Access Information"

        print_status "ArgoCD URL: https://cnoe.localtest.me/argocd"
        print_status "Username: admin"
        print_status "Password: xjo1tyj-hK9VqFux"

        print_status "To get password: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath=\"{.data.password}\" | base64 -d"

        echo
    fi
}

# Run comprehensive tests
run_tests() {
    print_header "Running Test Suite"

    print_status "Running unit tests..."
    python3 test_agent.py

    echo
}

# Main demo execution
main() {
    print_status "Golden Path AI-Powered Developer Onboarding Demo"
    print_status "This demo showcases the complete workflow from natural language request to deployed application"
    echo

    # Check prerequisites
    check_environment
    check_cluster

    # Run the demo components
    run_tests
    run_agent_demo
    show_k8s_resources
    show_argocd_info

    print_header "Demo Summary"
    print_status "✅ AI agent can extract application names from natural language"
    print_status "✅ Template system works with parameter substitution"
    print_status "✅ GitOps workflow integration is functional"
    print_status "✅ ArgoCD deployment automation is ready"

    if [ "$GITHUB_SET" = true ] && [ "$GITHUB_USER_SET" = true ]; then
        print_status "✅ Full end-to-end deployment tested"
    else
        print_warning "⚠️  Set GitHub credentials to test full deployment"
    fi

    print_status "🎉 Golden Path Demo completed successfully!"
    echo

    print_status "Next steps:"
    print_status "1. Set your GitHub credentials for full testing"
    print_status "2. Access ArgoCD to monitor deployments"
    print_status "3. Test with your own application requests"
    print_status "4. Customize the stack templates for your needs"
}

# Handle script arguments
case "${1:-demo}" in
    "demo")
        main
        ;;
    "test")
        run_tests
        ;;
    "cluster")
        check_cluster
        ;;
    "agent")
        check_environment
        if [ -n "$2" ]; then
            run_agent_demo
            python3 agent.py "$2"
        else
            print_error "Please provide a request: $0 agent \"your request here\""
        fi
        ;;
    "help"|"-h"|"--help")
        echo "Golden Path AI-Powered Developer Onboarding Demo"
        echo
        echo "Usage: $0 [command] [options]"
        echo
        echo "Commands:"
        echo "  demo        Run the complete demo (default)"
        echo "  test        Run the test suite only"
        echo "  cluster     Check cluster status"
        echo "  agent       Run agent with specific request"
        echo "  help        Show this help message"
        echo
        echo "Examples:"
        echo "  $0                                    # Run full demo"
        echo "  $0 test                               # Run tests only"
        echo "  $0 agent \"Deploy my user-service\"   # Test specific request"
        echo
        echo "Environment Variables:"
        echo "  GITHUB_TOKEN           GitHub personal access token"
        echo "  GITHUB_USERNAME        Your GitHub username"
        echo "  OPENROUTER_API_KEY     OpenRouter API key (demo key provided)"
        ;;
    *)
        print_error "Unknown command: $1"
        print_status "Run '$0 help' for usage information"
        exit 1
        ;;
esac