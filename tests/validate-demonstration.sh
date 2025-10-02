#!/bin/bash

# Golden Path Demo - Comprehensive Validation Script
# Validates all phases of the demonstration setup

set -e
set -u

# Test colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Validation results
PASSED=0
FAILED=0
WARNINGS=0
TOTAL_VALIDATIONS=0

# Test configuration
APP_NAME="inventory-api"
VALIDATION_REPORT="/tmp/demonstration-validation-report.json"
TEMP_DIR="/tmp/golden-path-validation"

# Create temp directory
mkdir -p "$TEMP_DIR"

# Validation functions
validate_prerequisite() {
    local test_name="$1"
    local test_command="$2"
    local critical="${3:-true}"

    TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
    echo -n "  Validating $test_name... "

    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo -e "${RED}✗ FAIL${NC}"
            FAILED=$((FAILED + 1))
        else
            echo -e "${YELLOW}⚠ WARNING${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
        echo "    Command: $test_command"
        return 1
    fi
}

validate_file() {
    local file_path="$1"
    local description="$2"
    local critical="${3:-true}"

    TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
    echo -n "  Validating $description... "

    if [ -f "$file_path" ]; then
        echo -e "${GREEN}✓ EXISTS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo -e "${RED}✗ MISSING${NC}"
            FAILED=$((FAILED + 1))
        else
            echo -e "${YELLOW}⚠ MISSING${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
        echo "    Path: $file_path"
        return 1
    fi
}

validate_directory() {
    local dir_path="$1"
    local description="$2"
    local critical="${3:-true}"

    TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
    echo -n "  Validating $description... "

    if [ -d "$dir_path" ]; then
        echo -e "${GREEN}✓ EXISTS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo -e "${RED}✗ MISSING${NC}"
            FAILED=$((FAILED + 1))
        else
            echo -e "${YELLOW}⚠ MISSING${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
        echo "    Path: $dir_path"
        return 1
    fi
}

validate_service() {
    local service_name="$1"
    local namespace="${2:-default}"
    local critical="${3:-true}"

    TOTAL_VALIDATIONS=$((TOTAL_VALIDATIONS + 1))
    echo -n "  Validating service $service_name... "

    if kubectl get service "$service_name" -n "$namespace" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ RUNNING${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo -e "${RED}✗ NOT FOUND${NC}"
            FAILED=$((FAILED + 1))
        else
            echo -e "${YELLOW}⚠ NOT FOUND${NC}"
            WARNINGS=$((WARNINGS + 1))
        fi
        return 1
    fi
}

print_section() {
    local section_name="$1"
    echo ""
    echo "========================================"
    echo "$section_name"
    echo "========================================"
}

# Main validation script
echo "========================================"
echo "Golden Path Demo - Demonstration Validation"
echo "========================================"
echo "Timestamp: $(date -Iseconds)"
echo ""

# Phase 1: Prerequisites Validation
print_section "PHASE 1: PREREQUISITES VALIDATION"

echo "Validating system prerequisites..."

validate_prerequisite "Docker Installation" \
    "docker --version"

validate_prerequisite "Docker Daemon" \
    "docker info"

validate_prerequisite "kubectl Installation" \
    "kubectl version --client"

validate_prerequisite "kubectl Cluster Access" \
    "kubectl cluster-info"

validate_prerequisite "Git Installation" \
    "git --version"

validate_prerequisite "Python Installation" \
    "python3 --version | grep -E 'Python 3\.[9-9]|[1-9][0-9]'" \
    false

validate_prerequisite "GitHub Token" \
    "test -n \"\${GITHUB_TOKEN:-}\""

validate_prerequisite "GitHub Username" \
    "test -n \"\${GITHUB_USERNAME:-}\""

validate_prerequisite "OpenAI API Key" \
    "test -n \"\${OPENAI_API_KEY:-}\""

# Phase 1: idpbuilder Validation
print_section "PHASE 1: IDPBUILDER VALIDATION"

echo "Validating idpbuilder installation and cluster..."

validate_directory "idpbuilder" "idpbuilder directory"

validate_file "idpbuilder/idpbuilder" "idpbuilder executable" \
    false

validate_prerequisite "Kubernetes Cluster Access" \
    "kubectl get nodes" \
    false

validate_prerequisite "ArgoCD Installation" \
    "kubectl get namespace argocd" \
    false

validate_prerequisite "ArgoCD Pods Running" \
    "kubectl get pods -n argocd | grep -q Running" \
    false

validate_prerequisite "Tekton Installation" \
    "kubectl get namespace tekton-pipelines" \
    false

# Phase 2: Stack Templates Validation
print_section "PHASE 2: STACK TEMPLATES VALIDATION"

echo "Validating Golden Path stack templates..."

validate_directory "cnoe-stacks" "Stacks directory" \
    false

validate_directory "cnoe-stacks/nodejs-template" "NodeJS template directory" \
    false

validate_directory "cnoe-stacks/nodejs-template/app-source" "App source directory" \
    false

validate_file "cnoe-stacks/nodejs-template/app-source/index.js" "NodeJS application file" \
    false

validate_file "cnoe-stacks/nodejs-template/app-source/package.json" "Package.json file" \
    false

validate_directory "cnoe-stacks/nodejs-gitops-template" "GitOps template directory" \
    false

validate_file "cnoe-stacks/nodejs-gitops-template/deployment.yaml" "Deployment manifest" \
    false

# Phase 3: Agent Validation
print_section "PHASE 3: ONBOARDING AGENT VALIDATION"

echo "Validating AI onboarding agent..."

validate_directory "agentic-onboarding-agent" "Agent directory" \
    false

validate_file "agentic-onboarding-agent/agent.py" "Agent script" \
    false

validate_prerequisite "Python Virtual Environment" \
    "test -d agentic-onboarding-agent/venv" \
    false

validate_prerequisite "Required Python Packages" \
    "python3 -c \"import os; os.chdir('agentic-onboarding-agent'); import openai, github, kubernetes\" 2>/dev/null" \
    false

# Sample Application Validation
print_section "SAMPLE APPLICATION VALIDATION"

echo "Validating sample application deployment..."

validate_service "${APP_NAME}-service" "default" \
    false

validate_prerequisite "Application Deployment" \
    "kubectl get deployment $APP_NAME -n default" \
    false

validate_prerequisite "Application Pods" \
    "kubectl get pods -l app=$APP_NAME -n default" \
    false

validate_prerequisite "ArgoCD Application" \
    "kubectl get application $APP_NAME -n argocd" \
    false

# Advanced Validations
print_section "ADVANCED VALIDATIONS"

echo "Performing advanced validations..."

# Validate NodeJS syntax
if [ -f "cnoe-stacks/nodejs-template/app-source/index.js" ]; then
    validate_prerequisite "NodeJS Syntax" \
        "node -c cnoe-stacks/nodejs-template/app-source/index.js" \
        false
fi

# Validate YAML syntax
if [ -f "cnoe-stacks/nodejs-gitops-template/deployment.yaml" ]; then
    validate_prerequisite "YAML Syntax" \
        "python3 -c \"import yaml; yaml.safe_load(open('cnoe-stacks/nodejs-gitops-template/deployment.yaml'))\"" \
        false
fi

# Validate template placeholders
if [ -f "cnoe-stacks/nodejs-gitops-template/deployment.yaml" ]; then
    validate_prerequisite "Template Placeholders" \
        "grep -q '{{.Values.appName}}' cnoe-stacks/nodejs-gitops-template/deployment.yaml" \
        false
fi

# Validate cluster connectivity
validate_prerequisite "Cluster Connectivity" \
    "kubectl get pods -A | head -n 5" \
    false

# Summary
print_section "VALIDATION SUMMARY"

echo "Total Validations: $TOTAL_VALIDATIONS"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Warnings: $WARNINGS${NC}"

if [ $FAILED -eq 0 ]; then
    SUCCESS_RATE=100
    echo -e "${GREEN}✅ ALL CRITICAL VALIDATIONS PASSED${NC}"
    echo -e "${GREEN}✅ DEMONSTRATION READY${NC}"
else
    SUCCESS_RATE=$(( (PASSED * 100) / TOTAL_VALIDATIONS ))
    echo -e "${YELLOW}Success Rate: $SUCCESS_RATE%${NC}"
    if [ $SUCCESS_RATE -lt 95 ]; then
        echo -e "${RED}❌ DEMONSTRATION NOT READY - Success rate below 95%${NC}"
    else
        echo -e "${YELLOW}⚠️ DEMONSTRATION READY WITH WARNINGS${NC}"
    fi
fi

# Go/No-Go Recommendation
echo ""
echo "========================================"
echo "DEMONSTRATION READINESS ASSESSMENT"
echo "========================================"

if [ $FAILED -eq 0 ] && [ $SUCCESS_RATE -ge 95 ]; then
    echo -e "${GREEN}🟢 GO - Demonstration is ready${NC}"
    echo "All critical validations passed successfully."
    echo "The demonstration can proceed with confidence."
elif [ $FAILED -le 2 ] && [ $SUCCESS_RATE -ge 90 ]; then
    echo -e "${YELLOW}🟡 CAUTION - Demonstration ready with minor issues${NC}"
    echo "Some validations failed but may not impact demonstration success."
    echo "Review failed validations and proceed with caution."
else
    echo -e "${RED}🔴 NO-GO - Demonstration not ready${NC}"
    echo "Multiple critical validations failed."
    echo "Address issues before proceeding with demonstration."
fi

# Recommendations
echo ""
echo "========================================"
echo "RECOMMENDATIONS"
echo "========================================"

if [ $FAILED -gt 0 ]; then
    echo "Critical Issues to Address:"
    echo "- Fix failed validations before proceeding"
    echo "- Ensure all environment variables are set"
    echo "- Verify cluster connectivity and configuration"
fi

if [ $WARNINGS -gt 0 ]; then
    echo "Optional Improvements:"
    echo "- Address warnings for better demonstration experience"
    echo "- Consider installing optional components"
fi

if [ $FAILED -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✅ System is fully prepared for demonstration"
    echo "✅ All components validated successfully"
    echo "✅ Ready to proceed with Golden Path demo"
fi

# Generate JSON Report
cat > "$VALIDATION_REPORT" << EOF
{
  "validation_type": "Demonstration Readiness",
  "timestamp": "$(date -Iseconds)",
  "app_name": "$APP_NAME",
  "environment": {
    "docker_available": $(command -v docker >/dev/null 2>&1 && echo true || echo false),
    "kubectl_available": $(command -v kubectl >/dev/null 2>&1 && echo true || echo false),
    "git_available": $(command -v git >/dev/null 2>&1 && echo true || echo false),
    "github_token_configured": $(test -n "${GITHUB_TOKEN:-}" && echo true || echo false),
    "openai_key_configured": $(test -n "${OPENAI_API_KEY:-}" && echo true || echo false),
    "cluster_accessible": $(kubectl cluster-info >/dev/null 2>&1 && echo true || echo false)
  },
  "validation_results": {
    "total_validations": $TOTAL_VALIDATIONS,
    "passed_validations": $PASSED,
    "failed_validations": $FAILED,
    "warning_validations": $WARNINGS,
    "success_rate": $SUCCESS_RATE
  },
  "readiness_status": {
    "ready": $([ $FAILED -eq 0 ] && [ $SUCCESS_RATE -ge 95 ] && echo true || echo false),
    "go_no_go": "$([ $FAILED -eq 0 ] && [ $SUCCESS_RATE -ge 95 ] && echo "GO" || [ $FAILED -le 2 ] && [ $SUCCESS_RATE -ge 90 ] && echo "CAUTION" || echo "NO-GO")"
  },
  "components_validated": {
    "prerequisites": {
      "docker": $(command -v docker >/dev/null 2>&1 && echo true || echo false),
      "kubectl": $(command -v kubectl >/dev/null 2>&1 && echo true || echo false),
      "git": $(command -v git >/dev/null 2>&1 && echo true || echo false),
      "python": $(command -v python3 >/dev/null 2>&1 && echo true || echo false)
    },
    "idpbuilder": {
      "installed": $(test -d "idpbuilder" && echo true || echo false),
      "cluster_accessible": $(kubectl cluster-info >/dev/null 2>&1 && echo true || echo false),
      "argocd_installed": $(kubectl get namespace argocd >/dev/null 2>&1 && echo true || echo false)
    },
    "stack_templates": {
      "template_directory_exists": $(test -d "cnoe-stacks" && echo true || echo false),
      "nodejs_template_exists": $(test -d "cnoe-stacks/nodejs-template" && echo true || echo false),
      "gitops_template_exists": $(test -d "cnoe-stacks/nodejs-gitops-template" && echo true || echo false)
    },
    "agent": {
      "agent_directory_exists": $(test -d "agentic-onboarding-agent" && echo true || echo false),
      "agent_script_exists": $(test -f "agentic-onboarding-agent/agent.py" && echo true || echo false)
    }
  },
  "recommendations": [
$(if [ $FAILED -gt 0 ]; then
    echo "    \"Address critical validation failures before proceeding\""
fi)
$(if [ $WARNINGS -gt 0 ]; then
    echo "    \"Consider addressing warnings for optimal demonstration experience\""
fi)
$(if [ $FAILED -eq 0 ]; then
    echo "    \"System ready for demonstration\""
fi)
  ]
}
EOF

echo ""
echo "Validation report saved to: $VALIDATION_REPORT"

# Clean up
rm -rf "$TEMP_DIR"

# Exit with appropriate code
if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 Demonstration validation completed successfully${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Demonstration validation failed${NC}"
    echo "Please address the issues above before proceeding."
    exit 1
fi