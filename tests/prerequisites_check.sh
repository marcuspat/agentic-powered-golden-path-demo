#!/bin/bash
# Golden Path Demo - Prerequisites Validation Script
# Validates all required tools, permissions, and environment setup

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Test results
PREREQ_RESULTS=()
FAILED_CHECKS=0

# Function to add test result
add_result() {
    local test_name="$1"
    local status="$2"
    local details="$3"

    PREREQ_RESULTS+=("$test_name|$status|$details")

    if [[ "$status" == "FAIL" ]]; then
        ((FAILED_CHECKS++))
        log_error "$test_name: $details"
    elif [[ "$status" == "WARN" ]]; then
        log_warning "$test_name: $details"
    else
        log_success "$test_name: $details"
    fi
}

# Function to check if command exists
check_command() {
    local cmd="$1"
    local min_version="${2:-}"

    if command -v "$cmd" &> /dev/null; then
        local version_output
        case "$cmd" in
            "docker")
                version_output=$(docker --version 2>/dev/null || echo "Unknown version")
                ;;
            "kubectl")
                version_output=$(kubectl version --client --short 2>/dev/null || echo "Unknown version")
                ;;
            "git")
                version_output=$(git --version 2>/dev/null || echo "Unknown version")
                ;;
            "python3"|"python")
                version_output=$("$cmd" --version 2>/dev/null || echo "Unknown version")
                ;;
            "pip3"|"pip")
                version_output=$("$cmd" --version 2>/dev/null || echo "Unknown version")
                ;;
            *)
                version_output=$("$cmd" --version 2>/dev/null || echo "Unknown version")
                ;;
        esac

        add_result "$cmd Installation" "PASS" "$version_output"
        return 0
    else
        add_result "$cmd Installation" "FAIL" "Command not found in PATH"
        return 1
    fi
}

# Function to check environment variables
check_env_var() {
    local var_name="$1"
    local var_value="${!var_name:-}"

    if [[ -n "$var_value" ]]; then
        # Hide sensitive values
        local display_value
        case "$var_name" in
            *TOKEN*|*KEY*|*SECRET*)
                display_value="***SET***"
                ;;
            *)
                display_value="$var_value"
                ;;
        esac
        add_result "Environment Variable: $var_name" "PASS" "$display_value"
        return 0
    else
        add_result "Environment Variable: $var_name" "FAIL" "Not set"
        return 1
    fi
}

# Function to check Docker functionality
check_docker_functionality() {
    log "Checking Docker functionality..."

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        add_result "Docker Daemon" "FAIL" "Docker daemon is not running"
        return 1
    fi

    # Test Docker pull
    local test_image="hello-world"
    if docker pull "$test_image" &> /dev/null; then
        add_result "Docker Pull" "PASS" "Successfully pulled $test_image"
        docker rmi "$test_image" &> /dev/null || true
    else
        add_result "Docker Pull" "WARN" "Failed to pull test image (network issues?)"
    fi

    # Check available disk space
    local available_space
    available_space=$(df -h /var/lib/docker 2>/dev/null | awk 'NR==2 {print $4}' || echo "Unknown")
    add_result "Docker Disk Space" "PASS" "Available: $available_space"
}

# Function to check Kubernetes cluster access
check_kubernetes() {
    log "Checking Kubernetes cluster access..."

    # Check if kubeconfig exists
    if [[ ! -f "$HOME/.kube/config" ]]; then
        add_result "Kubeconfig" "WARN" "No kubeconfig found at $HOME/.kube/config"
    else
        add_result "Kubeconfig" "PASS" "Found at $HOME/.kube/config"
    fi

    # Test cluster access
    if kubectl cluster-info &> /dev/null; then
        add_result "Cluster Access" "PASS" "Successfully connected to cluster"

        # Get cluster info
        local cluster_info
        cluster_info=$(kubectl cluster-info --request-timeout=10 2>/dev/null || echo "Timeout getting cluster info")
        add_result "Cluster Info" "PASS" "Cluster accessible"

        # Check nodes
        local node_count
        node_count=$(kubectl get nodes --no-headers 2>/dev/null | wc -l || echo "0")
        if [[ "$node_count" -gt 0 ]]; then
            add_result "Cluster Nodes" "PASS" "$node_count node(s) available"
        else
            add_result "Cluster Nodes" "WARN" "No nodes found in cluster"
        fi
    else
        add_result "Cluster Access" "FAIL" "Cannot connect to Kubernetes cluster"
    fi
}

# Function to check GitHub access
check_github_access() {
    log "Checking GitHub API access..."

    local github_token="${GITHUB_TOKEN:-}"

    if [[ -n "$github_token" ]]; then
        # Test GitHub API access
        local api_response
        api_response=$(curl -s -H "Authorization: token $github_token" \
                       https://api.github.com/user 2>/dev/null || echo "")

        if [[ -n "$api_response" ]] && echo "$api_response" | grep -q "login"; then
            local username
            username=$(echo "$api_response" | grep '"login"' | cut -d'"' -f4)
            add_result "GitHub API Access" "PASS" "Authenticated as: $username"

            # Check repository creation permissions
            local repo_perms
            repo_perms=$(echo "$api_response" | grep -o '"repo":[^,]*' | cut -d':' -f2 | tr -d '"' || echo "unknown")
            add_result "GitHub Repo Permissions" "PASS" "Repo permissions: $repo_perms"
        else
            add_result "GitHub API Access" "FAIL" "Invalid or expired token"
        fi
    else
        add_result "GitHub API Access" "FAIL" "GITHUB_TOKEN not set"
    fi
}

# Function to check Python environment
check_python_environment() {
    log "Checking Python environment..."

    # Check Python version
    local python_version
    if command -v python3 &> /dev/null; then
        python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>/dev/null || echo "Unknown")
        add_result "Python Version" "PASS" "Python $python_version"

        # Check minimum version requirement (3.9+)
        local major_minor
        major_minor=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
            add_result "Python Version Check" "PASS" "Meets minimum requirement (>=3.9)"
        else
            add_result "Python Version Check" "FAIL" "Python $major_minor is below minimum requirement (3.9)"
        fi
    else
        add_result "Python Version" "FAIL" "Python3 not found"
        return 1
    fi

    # Check pip
    if command -v pip3 &> /dev/null; then
        local pip_version
        pip_version=$(pip3 --version 2>/dev/null || echo "Unknown")
        add_result "Pip Version" "PASS" "$pip_version"
    else
        add_result "Pip Version" "FAIL" "pip3 not found"
    fi

    # Check key Python packages that will be needed
    local required_packages=("PyGithub" "kubernetes" "requests")
    for package in "${required_packages[@]}"; do
        if python3 -c "import $package" 2>/dev/null; then
            add_result "Python Package: $package" "PASS" "Already installed"
        else
            add_result "Python Package: $package" "WARN" "Not installed (will be installed later)"
        fi
    done
}

# Function to check system resources
check_system_resources() {
    log "Checking system resources..."

    # Check available memory
    local available_memory
    available_memory=$(free -h 2>/dev/null | awk 'NR==2{print $7}' || echo "Unknown")
    add_result "Available Memory" "PASS" "$available_memory"

    # Check available disk space
    local available_disk
    available_disk=$(df -h . 2>/dev/null | awk 'NR==2{print $4}' || echo "Unknown")
    add_result "Available Disk Space" "PASS" "$available_disk"

    # Check CPU cores
    local cpu_cores
    cpu_cores=$(nproc 2>/dev/null || echo "Unknown")
    add_result "CPU Cores" "PASS" "$cpu_cores cores"
}

# Function to check network connectivity
check_network_connectivity() {
    log "Checking network connectivity..."

    # Check internet connectivity
    if curl -s --connect-timeout 5 https://www.google.com > /dev/null 2>&1; then
        add_result "Internet Connectivity" "PASS" "Can reach external sites"
    else
        add_result "Internet Connectivity" "WARN" "Limited or no internet connectivity"
    fi

    # Check GitHub connectivity
    if curl -s --connect-timeout 5 https://api.github.com > /dev/null 2>&1; then
        add_result "GitHub Connectivity" "PASS" "Can reach GitHub API"
    else
        add_result "GitHub Connectivity" "FAIL" "Cannot reach GitHub API"
    fi

    # Check Docker Hub connectivity
    if curl -s --connect-timeout 5 https://registry-1.docker.io/v2/ > /dev/null 2>&1; then
        add_result "Docker Hub Connectivity" "PASS" "Can reach Docker Hub"
    else
        add_result "Docker Hub Connectivity" "WARN" "Cannot reach Docker Hub (may affect image pulls)"
    fi
}

# Function to generate summary report
generate_summary() {
    log "\n" "=" * 60
    log "PREREQUISITES VALIDATION SUMMARY"
    log "=" * 60

    local total_checks=${#PREREQ_RESULTS[@]}
    local passed_checks=0
    local warning_checks=0

    for result in "${PREREQ_RESULTS[@]}"; do
        local status=$(echo "$result" | cut -d'|' -f2)
        case "$status" in
            "PASS") ((passed_checks++)) ;;
            "WARN") ((warning_checks++)) ;;
        esac
    done

    echo
    log "Total Checks: $total_checks"
    log_success "Passed: $passed_checks"
    log_warning "Warnings: $warning_checks"
    log_error "Failed: $FAILED_CHECKS"

    # Calculate success rate
    local success_rate=0
    if [[ $total_checks -gt 0 ]]; then
        success_rate=$((passed_checks * 100 / total_checks))
    fi

    echo
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        if [[ $warning_checks -eq 0 ]]; then
            log_success "🎉 ALL PREREQUISITES SATISFIED ($success_rate%)"
            log "You're ready to proceed with the Golden Path demo!"
        else
            log_warning "⚠️  PREREQUISITES MOSTLY SATISFIED ($success_rate%)"
            log "Some warnings detected, but you should be able to proceed."
        fi
        return 0
    else
        log_error "❌ PREREQUISITES NOT MET ($success_rate%)"
        log "Please address the failed checks before proceeding."
        return 1
    fi
}

# Function to generate detailed report
generate_detailed_report() {
    local report_file="prerequisites_report_$(date +%Y%m%d_%H%M%S).json"

    log "\nGenerating detailed report: $report_file"

    cat > "$report_file" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "summary": {
    "total_checks": ${#PREREQ_RESULTS[@]},
    "passed_checks": $(( ${#PREREQ_RESULTS[@]} - FAILED_CHECKS - $(printf '%s\n' "${PREREQ_RESULTS[@]}" | grep -c "WARN" || echo 0) )),
    "warning_checks": $(printf '%s\n' "${PREREQ_RESULTS[@]}" | grep -c "WARN" || echo 0),
    "failed_checks": $FAILED_CHECKS,
    "success_rate": $(( (${#PREREQ_RESULTS[@]} - FAILED_CHECKS) * 100 / ${#PREREQ_RESULTS[@]} ))
  },
  "results": [
EOF

    local first=true
    for result in "${PREREQ_RESULTS[@]}"; do
        local test_name=$(echo "$result" | cut -d'|' -f1)
        local status=$(echo "$result" | cut -d'|' -f2)
        local details=$(echo "$result" | cut -d'|' -f3-)

        if [[ "$first" == "true" ]]; then
            first=false
        else
            echo "," >> "$report_file"
        fi

        cat >> "$report_file" << EOF
    {
      "test_name": "$test_name",
      "status": "$status",
      "details": "$details"
    }
EOF
    done

    cat >> "$report_file" << EOF
  ]
}
EOF

    log "Detailed report saved to: $report_file"
}

# Main execution
main() {
    log "Starting Golden Path Demo Prerequisites Validation"
    log "Timestamp: $(date)"

    # Core tool checks
    log "\n" "-" * 40
    log "CORE TOOL VALIDATION"
    log "-" * 40

    check_command "docker"
    check_command "kubectl"
    check_command "git"

    # Prefer python3, fallback to python
    if command -v python3 &> /dev/null; then
        check_command "python3"
        check_command "pip3"
    else
        check_command "python"
        check_command "pip"
    fi

    # Environment variable checks
    log "\n" "-" * 40
    log "ENVIRONMENT VARIABLE VALIDATION"
    log "-" * 40

    check_env_var "GITHUB_TOKEN"
    check_env_var "OPENAI_API_KEY"
    check_env_var "GITHUB_USERNAME"

    # Functionality checks
    log "\n" "-" * 40
    log "FUNCTIONALITY VALIDATION"
    log "-" * 40

    check_docker_functionality
    check_kubernetes
    check_github_access
    check_python_environment

    # System resource checks
    log "\n" "-" * 40
    log "SYSTEM RESOURCE VALIDATION"
    log "-" * 40

    check_system_resources
    check_network_connectivity

    # Generate reports
    generate_summary
    generate_detailed_report

    # Return appropriate exit code
    if [[ $FAILED_CHECKS -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi