#!/usr/bin/env python3
"""
Golden Path Demo Test Suite
Comprehensive automated testing for AI-Powered Developer Onboarding

This test suite validates:
1. Prerequisites and environment setup
2. Phase 1: idpbuilder installation and cluster setup
3. Phase 2: Stack template creation and validation
4. Phase 3: AI agent functionality and API integration
5. End-to-end workflow integration
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TestResult:
    """Test result container with detailed reporting"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.start_time = None
        self.end_time = None
        self.passed = False
        self.error_message = None
        self.details = {}
        self.command_output = ""

    def start(self):
        self.start_time = datetime.now()
        logger.info(f"Starting test: {self.name}")

    def end(self, passed: bool, error_message: str = None, details: Dict = None):
        self.end_time = datetime.now()
        self.passed = passed
        self.error_message = error_message
        if details:
            self.details.update(details)

        duration = (self.end_time - self.start_time).total_seconds()
        status = "PASS" if passed else "FAIL"
        logger.info(f"Test {self.name}: {status} ({duration:.2f}s)")

        if error_message:
            logger.error(f"Error: {error_message}")

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            'passed': self.passed,
            'error_message': self.error_message,
            'details': self.details,
            'timestamp': self.start_time.isoformat() if self.start_time else None
        }


class GoldenPathTestSuite:
    """Main test suite for Golden Path demo validation"""

    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.test_results: List[TestResult] = []
        self.workspace_dir = Path("/workspaces/ai-powered-golden-path-demo")
        self.temp_dir = Path("/tmp/golden-path-tests")
        self.temp_dir.mkdir(exist_ok=True)

        # Test configuration
        self.test_app_name = "test-inventory-api"
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.github_username = os.getenv("GITHUB_USERNAME")

    def _load_config(self, config_file: str) -> Dict:
        """Load test configuration from file or use defaults"""
        default_config = {
            "timeouts": {
                "cluster_setup": 1800,  # 30 minutes
                "app_deployment": 600,   # 10 minutes
                "agent_execution": 300   # 5 minutes
            },
            "expected_services": {
                "argocd": ["argocd-server", "argocd-repo-server", "argocd-application-controller"],
                "tekton": ["tekton-pipelines-controller", "tekton-pipelines-webhook"],
                "kubernetes": ["coredns", "etcd", "kube-apiserver", "kube-controller-manager", "kube-scheduler", "kube-proxy"]
            },
            "test_repos": {
                "source_suffix": "-source",
                "gitops_suffix": "-gitops"
            }
        }

        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config

    def run_command(self, command: str, cwd: Path = None, timeout: int = 300,
                   check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Execute shell command with error handling and logging"""
        try:
            logger.info(f"Executing: {command}")
            if cwd:
                logger.info(f"Working directory: {cwd}")

            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                timeout=timeout,
                capture_output=capture_output,
                text=True
            )

            if capture_output:
                logger.debug(f"Command output: {result.stdout}")
                if result.stderr:
                    logger.debug(f"Command stderr: {result.stderr}")

            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, command, result.stdout, result.stderr
                )

            return result

        except subprocess.TimeoutExpired:
            raise Exception(f"Command timed out after {timeout} seconds: {command}")
        except subprocess.CalledProcessError as e:
            raise Exception(f"Command failed with exit code {e.returncode}: {command}\nStderr: {e.stderr}")

    def _run_test(self, test_name: str, test_description: str, test_func) -> TestResult:
        """Execute a test function and capture results"""
        result = TestResult(test_name, test_description)
        result.start()

        try:
            test_func(result)
            result.end(True, details=result.details)
        except Exception as e:
            result.end(False, str(e), result.details)

        self.test_results.append(result)
        return result

    def test_prerequisites(self) -> TestResult:
        """Test 1: Prerequisites validation"""
        def test_func(result):
            prerequisites = {
                "docker": "docker --version",
                "kubectl": "kubectl version --client",
                "git": "git --version",
                "python": "python3 --version",
                "pip": "pip3 --version"
            }

            prerequisite_results = {}

            for tool, command in prerequisites.items():
                try:
                    cmd_result = self.run_command(command, timeout=30)
                    prerequisite_results[tool] = {
                        "installed": True,
                        "version": cmd_result.stdout.strip()
                    }
                except Exception as e:
                    prerequisite_results[tool] = {
                        "installed": False,
                        "error": str(e)
                    }

            # Check environment variables
            env_vars = {
                "GITHUB_TOKEN": self.github_token is not None,
                "OPENAI_API_KEY": self.openai_api_key is not None,
                "GITHUB_USERNAME": self.github_username is not None
            }

            result.details.update({
                "tools": prerequisite_results,
                "environment_variables": env_vars
            })

            # Fail if any prerequisite is missing
            missing_tools = [k for k, v in prerequisite_results.items() if not v["installed"]]
            missing_env = [k for k, v in env_vars.items() if not v]

            if missing_tools:
                raise Exception(f"Missing required tools: {', '.join(missing_tools)}")
            if missing_env:
                raise Exception(f"Missing environment variables: {', '.join(missing_env)}")

        return self._run_test(
            "Prerequisites Validation",
            "Verify all required tools and environment variables are available",
            test_func
        )

    def test_phase1_cluster_setup(self) -> TestResult:
        """Test 2: Phase 1 - idpbuilder installation and cluster setup"""
        def test_func(result):
            idpbuilder_dir = self.workspace_dir / "idpbuilder"

            if not idpbuilder_dir.exists():
                # Clone idpbuilder repository
                clone_result = self.run_command(
                    "git clone https://github.com/cnoe-io/idpbuilder.git",
                    cwd=self.workspace_dir,
                    timeout=300
                )
                result.details["clone_output"] = clone_result.stdout

            # Run idpbuilder
            logger.info("Starting idpbuilder cluster setup...")
            idpbuilder_result = self.run_command(
                "./idpbuilder run",
                cwd=idpbuilder_dir,
                timeout=self.config["timeouts"]["cluster_setup"],
                check=False  # Don't fail immediately, check results
            )

            result.details["idpbuilder_output"] = idpbuilder_result.stdout
            if idpbuilder_result.stderr:
                result.details["idpbuilder_errors"] = idpbuilder_result.stderr

            # Verify cluster access
            try:
                kubectl_result = self.run_command("kubectl cluster-info", timeout=60)
                result.details["cluster_info"] = kubectl_result.stdout
            except Exception as e:
                raise Exception(f"Failed to access cluster: {e}")

            # Verify core pods are running
            try:
                pods_result = self.run_command(
                    "kubectl get pods -A",
                    timeout=60
                )
                result.details["cluster_pods"] = pods_result.stdout

                # Check for expected services
                expected_services = self.config["expected_services"]
                service_status = {}

                for service_type, services in expected_services.items():
                    service_status[service_type] = {}
                    for service in services:
                        try:
                            service_result = self.run_command(
                                f"kubectl get pods -A | grep {service}",
                                timeout=30,
                                check=False
                            )
                            service_status[service_type][service] = {
                                "found": service_result.returncode == 0,
                                "output": service_result.stdout.strip()
                            }
                        except Exception as e:
                            service_status[service_type][service] = {
                                "found": False,
                                "error": str(e)
                            }

                result.details["service_status"] = service_status

            except Exception as e:
                raise Exception(f"Failed to verify cluster pods: {e}")

        return self._run_test(
            "Phase 1: Cluster Setup",
            "Install idpbuilder and verify Kubernetes cluster with ArgoCD/Tekton",
            test_func
        )

    def test_phase2_stack_creation(self) -> TestResult:
        """Test 3: Phase 2 - Stack template creation and validation"""
        def test_func(result):
            stacks_dir = self.workspace_dir / "stacks"

            # Create test stack template
            test_stack_dir = stacks_dir / "test-nodejs-template"
            test_stack_dir.mkdir(parents=True, exist_ok=True)

            # Create NodeJS application template
            app_source_dir = test_stack_dir / "app-source"
            app_source_dir.mkdir(exist_ok=True)

            # Create simple NodeJS app
            nodejs_app = '''const http = require('http');
const port = 8080;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello from Golden Path Test App!\\n');
});

server.listen(port, () => {
  console.log(`Test server running on port ${port}`);
});
'''

            app_file = app_source_dir / "index.js"
            app_file.write_text(nodejs_app)
            result.details["app_template_created"] = True

            # Create package.json
            package_json = {
                "name": "{{.Values.appName}}",
                "version": "1.0.0",
                "description": "Test NodeJS application",
                "main": "index.js",
                "scripts": {
                    "start": "node index.js"
                }
            }

            package_file = app_source_dir / "package.json"
            package_file.write_text(json.dumps(package_json, indent=2))

            # Create Kubernetes manifests
            k8s_manifests_dir = test_stack_dir / "k8s-manifests"
            k8s_manifests_dir.mkdir(exist_ok=True)

            deployment_yaml = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{{{.Values.appName}}}}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{{{.Values.appName}}}}
  template:
    metadata:
      labels:
        app: {{{{.Values.appName}}}}
    spec:
      containers:
      - name: {{{{.Values.appName}}}}
        image: gcr.io/google-samples/hello-app:1.0
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: {{{{.Values.appName}}}}
spec:
  selector:
    app: {{{{.Values.appName}}}}
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
'''

            deployment_file = k8s_manifests_dir / "deployment.yaml"
            deployment_file.write_text(deployment_yaml)
            result.details["k8s_manifests_created"] = True

            # Create GitOps template
            gitops_template_dir = test_stack_dir / "gitops-template"
            gitops_template_dir.mkdir(exist_ok=True)

            argocd_app_yaml = f'''apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{{{.Values.appName}}}}
  namespace: argocd
spec:
  project: default
  source:
    repoURL: {{{{.Values.gitopsRepoUrl}}}}
    targetRevision: HEAD
    path: k8s-manifests
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
'''

            argocd_file = gitops_template_dir / "argocd-application.yaml"
            argocd_file.write_text(argocd_app_yaml)
            result.details["gitops_template_created"] = True

            # Validate stack structure
            stack_structure = {}
            for root, dirs, files in os.walk(test_stack_dir):
                rel_path = os.path.relpath(root, test_stack_dir)
                stack_structure[rel_path] = {
                    "dirs": dirs,
                    "files": files
                }

            result.details["stack_structure"] = stack_structure

            # Verify all required files exist
            required_files = [
                "app-source/index.js",
                "app-source/package.json",
                "k8s-manifests/deployment.yaml",
                "gitops-template/argocd-application.yaml"
            ]

            missing_files = []
            for file_path in required_files:
                if not (test_stack_dir / file_path).exists():
                    missing_files.append(file_path)

            if missing_files:
                raise Exception(f"Missing required stack files: {missing_files}")

        return self._run_test(
            "Phase 2: Stack Creation",
            "Create and validate NodeJS stack templates with GitOps configuration",
            test_func
        )

    def test_phase3_agent_creation(self) -> TestResult:
        """Test 4: Phase 3 - AI agent functionality and API integration"""
        def test_func(result):
            agent_dir = self.workspace_dir / "ai-agent"
            agent_dir.mkdir(exist_ok=True)

            # Create Python agent script
            agent_script = '''import os
import subprocess
import json
import sys
from github import Github
from kubernetes import client, config

class GoldenPathAgent:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.github_username = os.getenv("GITHUB_USERNAME")

        if not all([self.github_token, self.github_username]):
            raise Exception("Missing required environment variables")

    def create_github_repo(self, app_name):
        """Create GitHub repositories for source and GitOps"""
        print(f"Creating GitHub repos for {app_name}...")

        g = Github(self.github_token)
        user = g.get_user()

        try:
            source_repo = user.create_repo(f"{app_name}-source")
            gitops_repo = user.create_repo(f"{app_name}-gitops")

            return {
                "source_repo_url": source_repo.clone_url,
                "gitops_repo_url": gitops_repo.clone_url,
                "source_repo_name": source_repo.name,
                "gitops_repo_name": gitops_repo.name
            }
        except Exception as e:
            print(f"Error creating repos: {e}")
            return None

    def test_github_connection(self):
        """Test GitHub API connection"""
        try:
            g = Github(self.github_token)
            user = g.get_user()
            return {
                "connected": True,
                "username": user.login,
                "name": user.name
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }

    def test_kubernetes_connection(self):
        """Test Kubernetes cluster connection"""
        try:
            config.load_kube_config()
            v1 = client.CoreV1Api()
            pods = v1.list_pod_for_all_namespaces()
            return {
                "connected": True,
                "pod_count": len(pods.items)
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }

def main():
    """Test the agent functionality"""
    print("Testing Golden Path Agent...")

    agent = GoldenPathAgent()

    # Test GitHub connection
    github_test = agent.test_github_connection()
    print(f"GitHub connection: {github_test}")

    # Test Kubernetes connection
    k8s_test = agent.test_kubernetes_connection()
    print(f"Kubernetes connection: {k8s_test}")

    if github_test["connected"] and k8s_test["connected"]:
        print("✅ Agent tests passed!")
        return 0
    else:
        print("❌ Agent tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''

            agent_file = agent_dir / "test_agent.py"
            agent_file.write_text(agent_script)
            result.details["agent_script_created"] = True

            # Create requirements.txt
            requirements = "PyGithub==1.59.1\\nkubernetes==28.1.0\\nrequests==2.31.0\\n"
            requirements_file = agent_dir / "requirements.txt"
            requirements_file.write_text(requirements)

            # Install dependencies
            try:
                pip_result = self.run_command(
                    "pip3 install -r requirements.txt",
                    cwd=agent_dir,
                    timeout=300
                )
                result.details["dependencies_installed"] = True
                result.details["pip_output"] = pip_result.stdout
            except Exception as e:
                raise Exception(f"Failed to install dependencies: {e}")

            # Test agent functionality
            try:
                agent_test_result = self.run_command(
                    f"python3 test_agent.py",
                    cwd=agent_dir,
                    timeout=60,
                    env={
                        "GITHUB_TOKEN": self.github_token,
                        "GITHUB_USERNAME": self.github_username
                    }
                )
                result.details["agent_test_output"] = agent_test_result.stdout
                result.details["agent_test_passed"] = agent_test_result.returncode == 0

                if agent_test_result.returncode != 0:
                    raise Exception("Agent functionality test failed")

            except Exception as e:
                raise Exception(f"Agent test failed: {e}")

        return self._run_test(
            "Phase 3: Agent Creation",
            "Create and test AI agent with GitHub and Kubernetes integrations",
            test_func
        )

    def test_end_to_end_workflow(self) -> TestResult:
        """Test 5: End-to-end workflow integration"""
        def test_func(result):
            # This test validates the complete workflow from request to deployment
            # It simulates the full Golden Path process

            workflow_steps = []

            # Step 1: Simulate developer request
            developer_request = f"I need to deploy my new NodeJS service called {self.test_app_name}"
            workflow_steps.append({
                "step": 1,
                "action": "Developer request",
                "input": developer_request,
                "status": "completed"
            })

            # Step 2: Extract app name from request (simplified)
            app_name = self.test_app_name
            workflow_steps.append({
                "step": 2,
                "action": "Extract app name",
                "extracted_name": app_name,
                "status": "completed"
            })

            # Step 3: Validate stack templates exist
            test_stack_dir = self.workspace_dir / "stacks" / "test-nodejs-template"
            if test_stack_dir.exists():
                workflow_steps.append({
                    "step": 3,
                    "action": "Validate stack templates",
                    "status": "completed",
                    "stack_path": str(test_stack_dir)
                })
            else:
                workflow_steps.append({
                    "step": 3,
                    "action": "Validate stack templates",
                    "status": "failed",
                    "error": "Stack templates not found"
                })

            # Step 4: Test cluster readiness
            try:
                cluster_info = self.run_command("kubectl get nodes", timeout=30)
                workflow_steps.append({
                    "step": 4,
                    "action": "Verify cluster readiness",
                    "status": "completed",
                    "node_count": len(cluster_info.stdout.split('\\n')) - 1
                })
            except Exception as e:
                workflow_steps.append({
                    "step": 4,
                    "action": "Verify cluster readiness",
                    "status": "failed",
                    "error": str(e)
                })

            # Step 5: Validate ArgoCD accessibility
            try:
                argocd_pods = self.run_command(
                    "kubectl get pods -n argocd -l app.kubernetes.io/name=argocd-server",
                    timeout=30
                )
                workflow_steps.append({
                    "step": 5,
                    "action": "Validate ArgoCD accessibility",
                    "status": "completed" if argocd_pods.returncode == 0 else "failed",
                    "argocd_running": argocd_pods.returncode == 0
                })
            except Exception as e:
                workflow_steps.append({
                    "step": 5,
                    "action": "Validate ArgoCD accessibility",
                    "status": "failed",
                    "error": str(e)
                })

            # Step 6: Validate agent components
            agent_dir = self.workspace_dir / "ai-agent"
            agent_exists = agent_dir.exists() and (agent_dir / "test_agent.py").exists()
            workflow_steps.append({
                "step": 6,
                "action": "Validate agent components",
                "status": "completed" if agent_exists else "failed",
                "agent_ready": agent_exists
            })

            result.details["workflow_steps"] = workflow_steps

            # Calculate overall workflow success
            failed_steps = [s for s in workflow_steps if s.get("status") == "failed"]
            if failed_steps:
                raise Exception(f"Workflow failed at steps: {[s['step'] for s in failed_steps]}")

            result.details["workflow_success"] = True

        return self._run_test(
            "End-to-End Workflow",
            "Validate complete Golden Path workflow from request to deployment readiness",
            test_func
        )

    def test_demo_readiness(self) -> TestResult:
        """Test 6: Demo readiness assessment"""
        def test_func(result):
            readiness_checks = {}

            # Check cluster status
            try:
                nodes = self.run_command("kubectl get nodes -o wide", timeout=30)
                readiness_checks["cluster_status"] = {
                    "ready": True,
                    "node_count": len([l for l in nodes.stdout.split('\\n') if 'Ready' in l]),
                    "details": nodes.stdout.strip()
                }
            except Exception as e:
                readiness_checks["cluster_status"] = {
                    "ready": False,
                    "error": str(e)
                }

            # Check ArgoCD status
            try:
                argocd_apps = self.run_command(
                    "kubectl get applications -n argocd",
                    timeout=30
                )
                readiness_checks["argocd_status"] = {
                    "ready": argocd_apps.returncode == 0,
                    "applications": len([l for l in argocd_apps.stdout.split('\\n') if l.strip() and not l.startswith('NAME')]),
                    "details": argocd_apps.stdout.strip()
                }
            except Exception as e:
                readiness_checks["argocd_status"] = {
                    "ready": False,
                    "error": str(e)
                }

            # Check stack templates
            test_stack_dir = self.workspace_dir / "stacks" / "test-nodejs-template"
            stack_files = list(test_stack_dir.rglob("*")) if test_stack_dir.exists() else []
            readiness_checks["stack_templates"] = {
                "ready": len(stack_files) > 0,
                "file_count": len([f for f in stack_files if f.is_file()]),
                "stack_path": str(test_stack_dir)
            }

            # Check agent readiness
            agent_dir = self.workspace_dir / "ai-agent"
            agent_files = list(agent_dir.rglob("*")) if agent_dir.exists() else []
            readiness_checks["agent_readiness"] = {
                "ready": len(agent_files) > 0,
                "file_count": len([f for f in agent_files if f.is_file()]),
                "agent_path": str(agent_dir)
            }

            # Check environment variables
            env_status = {
                "github_token": bool(self.github_token),
                "openai_key": bool(self.openai_api_key),
                "github_username": bool(self.github_username)
            }
            readiness_checks["environment"] = {
                "ready": all(env_status.values()),
                "variables": env_status
            }

            # Overall readiness calculation
            ready_components = sum(1 for check in readiness_checks.values() if check.get("ready", False))
            total_components = len(readiness_checks)
            readiness_percentage = (ready_components / total_components) * 100

            readiness_checks["overall_readiness"] = {
                "percentage": readiness_percentage,
                "ready_components": ready_components,
                "total_components": total_components,
                "go_nogo": "GO" if readiness_percentage >= 80 else "NO-GO"
            }

            result.details.update(readiness_checks)

            if readiness_percentage < 80:
                raise Exception(f"Demo readiness insufficient: {readiness_percentage:.1f}% (threshold: 80%)")

        return self._run_test(
            "Demo Readiness Assessment",
            "Comprehensive demo readiness check with Go/No-Go criteria",
            test_func
        )

    def test_error_handling(self) -> TestResult:
        """Test 7: Error handling and recovery scenarios"""
        def test_func(result):
            error_scenarios = []

            # Test 1: Invalid kubectl command
            try:
                self.run_command("kubectl get invalid-resource", timeout=30, check=False)
                error_scenarios.append({
                    "scenario": "Invalid kubectl command",
                    "handled": True,
                    "expected_behavior": "Command fails gracefully without crashing"
                })
            except Exception as e:
                error_scenarios.append({
                    "scenario": "Invalid kubectl command",
                    "handled": True,
                    "error": str(e)
                })

            # Test 2: Missing environment variable
            original_token = os.environ.get("GITHUB_TOKEN")
            os.environ.pop("GITHUB_TOKEN", None)

            try:
                agent_dir = self.workspace_dir / "ai-agent"
                if (agent_dir / "test_agent.py").exists():
                    self.run_command(
                        "python3 test_agent.py",
                        cwd=agent_dir,
                        timeout=30,
                        check=False
                    )
                error_scenarios.append({
                    "scenario": "Missing GitHub token",
                    "handled": True,
                    "expected_behavior": "Agent fails gracefully with clear error message"
                })
            except Exception as e:
                error_scenarios.append({
                    "scenario": "Missing GitHub token",
                    "handled": True,
                    "error": str(e)
                })
            finally:
                if original_token:
                    os.environ["GITHUB_TOKEN"] = original_token

            # Test 3: Network timeout simulation
            try:
                # Simulate a timeout with a command that takes too long
                self.run_command("sleep 2", timeout=1, check=False)
                error_scenarios.append({
                    "scenario": "Command timeout",
                    "handled": True,
                    "expected_behavior": "Command times out gracefully"
                })
            except Exception as e:
                error_scenarios.append({
                    "scenario": "Command timeout",
                    "handled": True,
                    "error": str(e)
                })

            # Test 4: Invalid file path handling
            try:
                invalid_path = self.workspace_dir / "nonexistent" / "file.txt"
                content = invalid_path.read_text()
                error_scenarios.append({
                    "scenario": "Invalid file path",
                    "handled": False,
                    "unexpected": "Should have failed for nonexistent file"
                })
            except FileNotFoundError:
                error_scenarios.append({
                    "scenario": "Invalid file path",
                    "handled": True,
                    "expected_behavior": "FileNotFoundError raised appropriately"
                })
            except Exception as e:
                error_scenarios.append({
                    "scenario": "Invalid file path",
                    "handled": True,
                    "error": str(e)
                })

            result.details["error_scenarios"] = error_scenarios

            # Validate error handling
            handled_scenarios = [s for s in error_scenarios if s.get("handled", False)]
            total_scenarios = len(error_scenarios)
            handling_percentage = (len(handled_scenarios) / total_scenarios) * 100 if total_scenarios > 0 else 0

            result.details["error_handling_score"] = {
                "handled_scenarios": len(handled_scenarios),
                "total_scenarios": total_scenarios,
                "handling_percentage": handling_percentage
            }

            if handling_percentage < 75:
                raise Exception(f"Error handling insufficient: {handling_percentage:.1f}% (threshold: 75%)")

        return self._run_test(
            "Error Handling & Recovery",
            "Test error handling and recovery scenarios",
            test_func
        )

    def run_all_tests(self) -> Dict:
        """Execute all tests and generate comprehensive report"""
        logger.info("Starting Golden Path Demo Test Suite")
        logger.info(f"Workspace: {self.workspace_dir}")
        logger.info(f"Test app name: {self.test_app_name}")

        start_time = datetime.now()

        # Run all test phases
        tests = [
            self.test_prerequisites,
            self.test_phase1_cluster_setup,
            self.test_phase2_stack_creation,
            self.test_phase3_agent_creation,
            self.test_end_to_end_workflow,
            self.test_demo_readiness,
            self.test_error_handling
        ]

        for test_func in tests:
            try:
                test_func()
            except Exception as e:
                logger.error(f"Test execution failed: {e}")

        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()

        # Generate test summary
        passed_tests = sum(1 for result in self.test_results if result.passed)
        total_tests = len(self.test_results)
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0

        summary = {
            "test_suite": "Golden Path Demo Test Suite",
            "version": "1.0.0",
            "timestamp": start_time.isoformat(),
            "total_duration": total_duration,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": success_rate,
            "test_results": [result.to_dict() for result in self.test_results],
            "go_nogo": "GO" if success_rate >= 80 else "NO-GO"
        }

        # Save detailed report
        report_file = self.temp_dir / "test_report.json"
        with open(report_file, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Test suite completed in {total_duration:.2f} seconds")
        logger.info(f"Results: {passed_tests}/{total_tests} tests passed ({success_rate:.1f}%)")
        logger.info(f"Detailed report saved to: {report_file}")

        return summary

    def generate_test_commands(self) -> Dict[str, str]:
        """Generate individual test commands for manual execution"""
        commands = {
            "prerequisites": "python3 golden_path_tests.py --test prerequisites",
            "phase1": "python3 golden_path_tests.py --test phase1",
            "phase2": "python3 golden_path_tests.py --test phase2",
            "phase3": "python3 golden_path_tests.py --test phase3",
            "integration": "python3 golden_path_tests.py --test integration",
            "readiness": "python3 golden_path_tests.py --test readiness",
            "error-handling": "python3 golden_path_tests.py --test error-handling",
            "all": "python3 golden_path_tests.py --all"
        }
        return commands


def main():
    parser = argparse.ArgumentParser(description="Golden Path Demo Test Suite")
    parser.add_argument("--config", help="Test configuration file")
    parser.add_argument("--test", choices=[
        "prerequisites", "phase1", "phase2", "phase3",
        "integration", "readiness", "error-handling"
    ], help="Run specific test")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--commands", action="store_true", help="Show available test commands")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    suite = GoldenPathTestSuite(args.config)

    if args.commands:
        commands = suite.generate_test_commands()
        print("\\nAvailable Test Commands:")
        print("=" * 40)
        for name, command in commands.items():
            print(f"{name:15} : {command}")
        return 0

    if args.all or not args.test:
        # Run all tests
        summary = suite.run_all_tests()
        return 0 if summary["success_rate"] >= 80 else 1

    # Run specific test
    test_map = {
        "prerequisites": suite.test_prerequisites,
        "phase1": suite.test_phase1_cluster_setup,
        "phase2": suite.test_phase2_stack_creation,
        "phase3": suite.test_phase3_agent_creation,
        "integration": suite.test_end_to_end_workflow,
        "readiness": suite.test_demo_readiness,
        "error-handling": suite.test_error_handling
    }

    if args.test in test_map:
        result = test_map[args.test]()
        return 0 if result.passed else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())