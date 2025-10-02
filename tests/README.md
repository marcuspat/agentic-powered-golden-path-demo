# Golden Path Demo Test Suite

Comprehensive automated testing framework for the AI-Powered Developer Onboarding Golden Path demo.

## Overview

This test suite validates the complete Golden Path workflow, ensuring all components work together seamlessly from developer request to deployed application.

## Test Architecture

The test suite follows a layered approach:

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Runner Framework                    │
├─────────────────────────────────────────────────────────────┤
│  Prerequisites │ Unit Tests │ Integration │ Performance │ Security │
├─────────────────────────────────────────────────────────────┤
│              Golden Path Demo Components                    │
└─────────────────────────────────────────────────────────────┘
```

## Test Components

### 1. Prerequisites Validation (`prerequisites_check.sh`)
- **Purpose**: Verify all required tools and environment setup
- **Coverage**: Docker, kubectl, git, Python, environment variables
- **Duration**: ~5 minutes
- **Critical**: Yes

### 2. Golden Path Tests (`golden_path_tests.py`)
- **Purpose**: Comprehensive testing of the Golden Path workflow
- **Coverage**: All three phases of the workflow
- **Duration**: ~15-30 minutes
- **Critical**: Yes

#### Test Cases:
- **Phase 1**: idpbuilder installation and cluster setup
- **Phase 2**: Stack template creation and validation
- **Phase 3**: AI agent functionality and API integration
- **Integration**: End-to-end workflow validation
- **Readiness**: Demo readiness assessment
- **Error Handling**: Recovery scenarios

### 3. Performance Tests (`performance_tests.py`)
- **Purpose**: System performance and resource usage validation
- **Coverage**: Command performance, concurrent load, memory usage
- **Duration**: ~10-15 minutes
- **Critical**: No

### 4. Security Scan (`security_scan.py`)
- **Purpose**: Security vulnerability assessment
- **Coverage**: Secrets scanning, dependency analysis, configuration security
- **Duration**: ~5-10 minutes
- **Critical**: No

### 5. Test Runner (`test_runner.py`)
- **Purpose**: Advanced test execution framework with CI/CD integration
- **Features**: Parallel execution, retry logic, comprehensive reporting
- **Duration**: Variable (depends on selected tests)
- **Critical**: Yes (framework)

## Quick Start

### Prerequisites

Set required environment variables:
```bash
export GITHUB_TOKEN="your_github_personal_access_token"
export OPENAI_API_KEY="your_openai_api_key"
export GITHUB_USERNAME="your_github_username"
```

### Running Tests

#### Full Test Suite
```bash
# Run all tests with comprehensive reporting
python3 tests/run-all-tests.py

# Run only critical tests (quick mode)
python3 tests/run-all-tests.py --quick

# Get help
python3 tests/run-all-tests.py --help
```

#### Individual Test Categories

**Phase 1: Platform Setup**
```bash
# Test system prerequisites
bash tests/test-phase1-prerequisites.sh

# Test idpbuilder installation (if implemented)
bash tests/test-phase1-idpbuilder.sh
```

**Phase 2: Stack Templates**
```bash
# Test stack template creation
bash tests/test-phase2-stack-creation.sh
```

**Phase 3: AI Agent**
```bash
# Test agent environment setup
bash tests/test-phase3-agent-env.sh

# Test agent functionality
python3 tests/test-phase3-agent-functionality.py
```

**Integration Tests**
```bash
# End-to-end workflow tests
python3 tests/test-integration-e2e.py
```

**Validation & Failure Modes**
```bash
# Comprehensive demonstration validation
bash tests/validate-demonstration.sh

# Failure mode and robustness testing
bash tests/test-failure-modes.sh
```

## Test Categories

### 1. Infrastructure Tests
- **Purpose**: Validate system prerequisites and platform setup
- **Coverage**: Docker, kubectl, git, authentication, cluster connectivity
- **Scripts**: `test-phase1-prerequisites.sh`, `test-phase1-idpbuilder.sh`

### 2. Unit Tests
- **Purpose**: Test individual components in isolation
- **Coverage**: Stack templates, AI agent functionality, environment validation
- **Scripts**: `test-phase2-stack-creation.sh`, `test-phase3-agent-functionality.py`

### 3. Integration Tests
- **Purpose**: Validate end-to-end workflow functionality
- **Coverage**: Complete deployment pipeline, service connectivity
- **Scripts**: `test-integration-e2e.py`

### 4. Validation Tests
- **Purpose**: Demonstration readiness assessment
- **Coverage**: All phases, success criteria, go/no-go determination
- **Scripts**: `validate-demonstration.sh`

### 5. Resilience Tests
- **Purpose**: Test error handling and recovery scenarios
- **Coverage**: Failure modes, error detection, graceful degradation
- **Scripts**: `test-failure-modes.sh`

## Test Reports

### Report Generation
All tests generate JSON reports saved to `/tmp/`:

- `/tmp/golden-path-test-report-{timestamp}.json` - Timestamped detailed report
- `/tmp/golden-path-test-report-latest.json` - Latest report
- `/tmp/prerequisites-test-report.json` - Prerequisites validation
- `/tmp/phase2-test-report.json` - Phase 2 validation
- `/tmp/integration-test-report.json` - Integration test results
- `/tmp/demonstration-validation-report.json` - Demonstration readiness
- `/tmp/failure-mode-test-report.json` - Failure mode analysis

### Report Structure
```json
{
  "test_run": {
    "timestamp": "2024-01-01T10:00:00",
    "duration_seconds": 120.5,
    "quick_mode": false
  },
  "summary": {
    "total_tests": 25,
    "passed_tests": 24,
    "failed_tests": 1,
    "success_rate": 96.0,
    "critical_success_rate": 100.0
  },
  "test_results": [...],
  "recommendations": [...],
  "go_no_go": "GO"
}
```

## Success Criteria

### Go/No-Go Decision Matrix

| Metric | GO | CAUTION | NO-GO |
|--------|----|---------|-------|
| Critical Success Rate | 100% | 90-99% | <90% |
| Overall Success Rate | ≥95% | 90-94% | <90% |
| Prerequisites | ✅ All | ⚠️ Minor | ❌ Critical |
| Integration Tests | ✅ All | ⚠️ Minor | ❌ Critical |

### Success Thresholds

- **Critical Components**: 100% success required
- **Overall System**: 95%+ success rate
- **Integration**: Complete workflow validation
- **Robustness**: 90%+ error handling success

## Environment Setup

### Required Variables
```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"  # GitHub Personal Access Token
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxx"  # OpenAI API Key
export GITHUB_USERNAME="your-username"           # GitHub Username
```

### System Requirements
- Docker Desktop installed and running
- kubectl installed and configured
- git installed and configured
- Python 3.9+ with pip
- Access to Kubernetes cluster (for integration tests)

### Optional Components
- idpbuilder installation (for full platform tests)
- ArgoCD UI access (for demonstration validation)
- Tekton pipelines (for complete CI/CD validation)

## Test Development

### Adding New Tests

1. **Follow naming convention**: `test-{category}-{description}.sh` or `.py`
2. **Include comprehensive coverage**: Test both success and failure scenarios
3. **Generate reports**: Save results to JSON format
4. **Use appropriate exit codes**: 0=success, 1=warning, 2=failure
5. **Include timeout handling**: Prevent hanging tests

### Test Script Template

```bash
#!/bin/bash
# Test: [Description]
# Purpose: [What this test validates]

set -e
set -u

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
PASSED=0
FAILED=0

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"

    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASS${NC} $test_name"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}✗ FAIL${NC} $test_name"
        FAILED=$((FAILED + 1))
    fi
}

# Run tests
run_test "Test Name" "test_command"

# Generate report
# ... JSON report generation ...

# Exit with appropriate code
exit $FAILED
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure scripts are executable
   ```bash
   chmod +x tests/*.sh tests/*.py
   ```

2. **Environment Variables Missing**: Check required variables
   ```bash
   env | grep -E "(GITHUB|OPENAI)"
   ```

3. **Cluster Connectivity Issues**: Verify kubectl configuration
   ```bash
   kubectl cluster-info
   ```

4. **Docker Issues**: Check Docker daemon
   ```bash
   docker info
   ```

### Debug Mode

Run tests with verbose output:
```bash
bash -x tests/test-phase1-prerequisites.sh
python3 -m pytest tests/test-phase3-agent-functionality.py -v
```

### Test Cleanup

Clean up test artifacts:
```bash
rm -f /tmp/*test-report*.json
rm -rf /tmp/golden-path-*/
```

## Continuous Integration

### CI/CD Pipeline Integration

```yaml
# Example GitHub Actions workflow
name: Golden Path Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install requests pyyaml
      - name: Run tests
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          python3 tests/run-all-tests.py
      - name: Upload test reports
        uses: actions/upload-artifact@v3
        with:
          name: test-reports
          path: /tmp/*test-report*.json
```

## Performance Metrics

### Target Metrics
- **Test Execution Time**: <5 minutes (full suite)
- **Quick Mode Time**: <2 minutes (critical tests only)
- **Success Rate**: >95% overall
- **Critical Success Rate**: 100%
- **Robustness Score**: >90%

### Benchmarking
Track test performance over time:
```bash
# Benchmark current performance
time python3 tests/run-all-tests.py

# Compare with previous runs
python3 tests/run-all-tests.py --compare-baseline
```

## Best Practices

### Test Execution
1. **Run tests frequently** - Validate changes continuously
2. **Check environment** - Ensure prerequisites before running
3. **Review reports** - Analyze failure patterns
4. **Update tests** - Keep tests in sync with implementation

### Test Maintenance
1. **Regular updates** - Update tests as system evolves
2. **Coverage monitoring** - Ensure comprehensive test coverage
3. **Performance tracking** - Monitor test execution times
4. **Documentation** - Keep test documentation current

### Quality Assurance
1. **Code review** - Review test changes thoroughly
2. **Automated validation** - Use CI/CD for automated testing
3. **Failure analysis** - Root cause analysis for test failures
4. **Continuous improvement** - Regular test suite enhancement

## Support

### Getting Help
- Review test logs and reports for detailed error information
- Check environment variables and system requirements
- Refer to the main project documentation
- Open an issue for test-related problems

### Contributing
- Follow established test patterns and conventions
- Include comprehensive test coverage for new features
- Update documentation for test changes
- Ensure all tests pass before submitting changes

For more detailed information, refer to the comprehensive testing strategy document: `docs/testing-strategy.md`.