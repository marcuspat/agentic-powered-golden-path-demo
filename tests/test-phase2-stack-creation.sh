#!/bin/bash

# Phase 2: Golden Path Stack Creation Tests
# Tests for stack template creation, NodeJS app, Kubernetes manifests

set -e
set -u

# Test colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test results
PASSED=0
FAILED=0
TOTAL_TESTS=0

# Configuration
STACK_DIR="./cnoe-stacks"
TEMPLATE_DIR="$STACK_DIR/nodejs-template"
GITOPS_TEMPLATE_DIR="$STACK_DIR/nodejs-gitops-template"
APP_NAME="test-app"

run_test() {
    local test_name="$1"
    local test_command="$2"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo -n "Testing $test_name... "

    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        FAILED=$((FAILED + 1))
        echo "  Command: $test_command"
        return 1
    fi
}

run_test_with_desc() {
    local test_name="$1"
    local description="$2"
    local test_command="$3"

    echo ""
    echo "=== $test_name ==="
    echo "Description: $description"
    run_test "$test_name" "$test_command"
}

# Helper function to create test stack structure
create_test_stack() {
    echo "Creating test stack structure..."

    # Create directories
    mkdir -p "$TEMPLATE_DIR/app-source"
    mkdir -p "$GITOPS_TEMPLATE_DIR"

    # Create NodeJS application
    cat > "$TEMPLATE_DIR/app-source/index.js" << 'EOF'
const http = require('http');
const port = process.env.PORT || 8080;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello from our Golden Path App!\n');
});

server.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
EOF

    # Create package.json
    cat > "$TEMPLATE_DIR/app-source/package.json" << EOF
{
  "name": "golden-path-app",
  "version": "1.0.0",
  "description": "A sample NodeJS application",
  "main": "index.js",
  "scripts": {
    "start": "node index.js",
    "test": "echo \"Error: no test specified\" && exit 1"
  },
  "keywords": [],
  "author": "",
  "license": "ISC"
}
EOF

    # Create Kubernetes deployment manifest
    cat > "$GITOPS_TEMPLATE_DIR/deployment.yaml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{.Values.appName}}
  namespace: {{.Values.namespace | default "default"}}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{.Values.appName}}
  template:
    metadata:
      labels:
        app: {{.Values.appName}}
    spec:
      containers:
      - name: {{.Values.appName}}
        image: nginx:alpine
        ports:
        - containerPort: 80
        env:
        - name: PORT
          value: "{{.Values.port | default \"8080\"}}"
---
apiVersion: v1
kind: Service
metadata:
  name: {{.Values.appName}}-service
  namespace: {{.Values.namespace | default "default"}}
spec:
  selector:
    app: {{.Values.appName}}
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: ClusterIP
EOF

    # Create README
    cat > "$TEMPLATE_DIR/README.md" << 'EOF'
# Golden Path NodeJS Template

This is a sample NodeJS application template for the Golden Path demo.

## Usage

```bash
npm install
npm start
```

The application will start on port 8080 by default.
EOF
}

# Main test suite
echo "========================================"
echo "Phase 2: Golden Path Stack Creation Tests"
echo "========================================"

# Clean up any existing test stack
if [ -d "$STACK_DIR" ]; then
    echo "Cleaning up existing test stack..."
    rm -rf "$STACK_DIR"
fi

# Create test stack structure
create_test_stack

# Directory Structure Tests
run_test_with_desc "Stack Directory Creation" \
    "Verify stack directories are created" \
    "test -d '$TEMPLATE_DIR' && test -d '$GITOPS_TEMPLATE_DIR'"

run_test_with_desc "App Source Directory" \
    "Verify app-source directory exists" \
    "test -d '$TEMPLATE_DIR/app-source'"

# NodeJS Application Tests
run_test_with_desc "NodeJS Application File" \
    "Verify index.js is created" \
    "test -f '$TEMPLATE_DIR/app-source/index.js'"

run_test_with_desc "NodeJS Syntax Validation" \
    "Validate NodeJS syntax" \
    "node -c '$TEMPLATE_DIR/app-source/index.js'"

run_test_with_desc "Package.json Creation" \
    "Verify package.json is created" \
    "test -f '$TEMPLATE_DIR/app-source/package.json'"

run_test_with_desc "Package.json Validation" \
    "Validate package.json syntax" \
    "python3 -c \"import json; json.load(open('$TEMPLATE_DIR/app-source/package.json'))\""

run_test_with_desc "Package.json Content" \
    "Verify package.json has required fields" \
    "python3 -c \"import json; pkg=json.load(open('$TEMPLATE_DIR/app-source/package.json')); assert pkg['name']; assert pkg['version']; assert pkg['main']\""

# Kubernetes Manifest Tests
run_test_with_desc "Kubernetes Deployment Manifest" \
    "Verify deployment.yaml is created" \
    "test -f '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

run_test_with_desc "YAML Syntax Validation" \
    "Validate YAML syntax" \
    "python3 -c \"import yaml; yaml.safe_load(open('$GITOPS_TEMPLATE_DIR/deployment.yaml'))\""

run_test_with_desc "Template Placeholders" \
    "Verify template placeholders exist" \
    "grep -q '{{.Values.appName}}' '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

run_test_with_desc "Kubernetes API Version" \
    "Verify correct Kubernetes API version" \
    "grep -q 'apiVersion: apps/v1' '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

run_test_with_desc "Deployment Resource Type" \
    "Verify deployment resource type" \
    "grep -q 'kind: Deployment' '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

run_test_with_desc "Service Resource Type" \
    "Verify service resource type" \
    "grep -q 'kind: Service' '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

# Template Processing Tests
run_test_with_desc "Template Variables" \
    "Verify template variables are used" \
    "grep -q '{{.Values.appName}}' '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

run_test_with_desc "Default Values" \
    "Verify default values are configured" \
    "grep -q 'default' '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

# Documentation Tests
run_test_with_desc "README Creation" \
    "Verify README is created" \
    "test -f '$TEMPLATE_DIR/README.md'"

run_test_with_desc "README Content" \
    "Verify README contains relevant content" \
    "grep -q 'Golden Path' '$TEMPLATE_DIR/README.md'"

# kubectl Validation Tests
run_test_with_desc "kubectl Dry Run Validation" \
    "Validate manifests with kubectl dry-run" \
    "kubectl apply --dry-run=client -f '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

run_test_with_desc "kubectl Dry Run with Values" \
    "Test template processing with sample values" \
    "kubectl apply --dry-run=client -f <(sed 's/{{.Values.appName}}/$APP_NAME/g' '$GITOPS_TEMPLATE_DIR/deployment.yaml')"

# File Permission Tests
run_test_with_desc "File Permissions" \
    "Verify files have correct permissions" \
    "test -r '$TEMPLATE_DIR/app-source/index.js' && test -r '$GITOPS_TEMPLATE_DIR/deployment.yaml'"

# Summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
echo "Total Tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All Phase 2 tests passed!${NC}"
    SUCCESS_RATE=100
else
    SUCCESS_RATE=$(( (PASSED * 100) / TOTAL_TESTS ))
    echo -e "${YELLOW}Success Rate: $SUCCESS_RATE%${NC}"
    if [ $SUCCESS_RATE -lt 95 ]; then
        echo -e "${RED}Warning: Success rate below 95% threshold${NC}"
    fi
fi

# Generate JSON report
cat > /tmp/phase2-test-report.json << EOF
{
  "test_phase": "Phase 2: Stack Creation",
  "timestamp": "$(date -Iseconds)",
  "total_tests": $TOTAL_TESTS,
  "passed_tests": $PASSED,
  "failed_tests": $FAILED,
  "success_rate": $SUCCESS_RATE,
  "stack_directory": "$STACK_DIR",
  "template_directory": "$TEMPLATE_DIR",
  "gitops_directory": "$GITOPS_TEMPLATE_DIR",
  "recommendations": [
$(if [ $FAILED -gt 0 ]; then
    echo "    \"Fix failed stack creation tests before proceeding\""
else
    echo "    \"Stack templates created successfully and validated\""
fi)
  ]
}
EOF

echo "Test report saved to: /tmp/phase2-test-report.json"

# Exit with error if any tests failed
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Error: $FAILED Phase 2 test(s) failed${NC}"
    exit 1
else
    echo -e "${GREEN}Success: All Phase 2 tests passed${NC}"
    exit 0
fi