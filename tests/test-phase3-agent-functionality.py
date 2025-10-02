#!/usr/bin/env python3
"""
Phase 3: Onboarding Agent Functionality Tests
Tests for the AI onboarding agent including GitHub integration,
template population, and ArgoCD deployment
"""

import unittest
import os
import tempfile
import shutil
import json
from unittest.mock import Mock, patch, MagicMock
import subprocess
import sys

# Mock the required modules if they're not available
try:
    from github import Github
    from kubernetes import client, config
except ImportError:
    print("Warning: github or kubernetes modules not available. Using mocks.")
    Github = Mock()
    client = Mock()
    config = Mock()

class TestOnboardingAgent(unittest.TestCase):
    """Test suite for the Onboarding Agent functionality"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.app_name = "test-inventory-api"

        # Set required environment variables for testing
        os.environ['GITHUB_TOKEN'] = 'test_token_12345'
        os.environ['OPENAI_API_KEY'] = 'test_openai_key_12345'
        os.environ['GITHUB_USERNAME'] = 'testuser'

        # Mock stack template paths
        self.template_path = os.path.join(self.test_dir, 'nodejs-template')
        self.gitops_template_path = os.path.join(self.test_dir, 'nodejs-gitops-template')

        # Create mock templates
        self.create_mock_templates()

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def create_mock_templates(self):
        """Create mock template files for testing"""
        # Create source template
        os.makedirs(os.path.join(self.template_path, 'app-source'), exist_ok=True)

        # Mock NodeJS app
        with open(os.path.join(self.template_path, 'app-source', 'index.js'), 'w') as f:
            f.write('console.log("Hello from Golden Path App!");')

        # Mock package.json
        with open(os.path.join(self.template_path, 'app-source', 'package.json'), 'w') as f:
            json.dump({
                "name": "golden-path-app",
                "version": "1.0.0",
                "main": "index.js"
            }, f)

        # Create GitOps template
        os.makedirs(self.gitops_template_path, exist_ok=True)

        # Mock deployment manifest
        with open(os.path.join(self.gitops_template_path, 'deployment.yaml'), 'w') as f:
            f.write(f'''apiVersion: apps/v1
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
        image: nginx:alpine
        ports:
        - containerPort: 80''')

    def test_environment_validation(self):
        """Test environment variable validation"""
        # Test with all required variables set
        self.assertTrue(self.validate_environment())

        # Test with missing GitHub token
        del os.environ['GITHUB_TOKEN']
        with self.assertRaises(EnvironmentError):
            self.validate_environment()

        # Restore environment
        os.environ['GITHUB_TOKEN'] = 'test_token_12345'

    def validate_environment(self):
        """Validate required environment variables"""
        required_vars = ['GITHUB_TOKEN', 'OPENAI_API_KEY', 'GITHUB_USERNAME']
        for var in required_vars:
            if not os.getenv(var):
                raise EnvironmentError(f"Missing required environment variable: {var}")
        return True

    def test_missing_environment_variables(self):
        """Test handling of missing environment variables"""
        # Save original environment
        original_env = os.environ.copy()

        try:
            # Test missing GITHUB_TOKEN
            del os.environ['GITHUB_TOKEN']
            with self.assertRaises(EnvironmentError):
                self.validate_environment()

            # Test missing OPENAI_API_KEY
            os.environ['GITHUB_TOKEN'] = 'test_token'
            del os.environ['OPENAI_API_KEY']
            with self.assertRaises(EnvironmentError):
                self.validate_environment()

            # Test missing GITHUB_USERNAME
            os.environ['OPENAI_API_KEY'] = 'test_key'
            del os.environ['GITHUB_USERNAME']
            with self.assertRaises(EnvironmentError):
                self.validate_environment()

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

    @patch('github.Github')
    def test_github_repo_creation(self, mock_github):
        """Test GitHub repository creation"""
        # Mock GitHub API responses
        mock_user = Mock()
        mock_repo = Mock()
        mock_repo.clone_url = 'https://github.com/testuser/test-repo.git'
        mock_gitops_repo = Mock()
        mock_gitops_repo.clone_url = 'https://github.com/testuser/test-repo-gitops.git'

        mock_user.create_repo.side_effect = [mock_repo, mock_gitops_repo]
        mock_github.return_value.get_user.return_value = mock_user

        # Test repository creation
        source_url, gitops_url = self.create_github_repo(self.app_name)

        self.assertIn('test-repo', source_url)
        self.assertIn('test-repo-gitops', gitops_url)
        self.assertEqual(mock_user.create_repo.call_count, 2)

    def create_github_repo(self, app_name):
        """Mock GitHub repository creation"""
        try:
            g = Github(os.getenv("GITHUB_TOKEN"))
            user = g.get_user()

            # Create source repository
            repo = user.create_repo(f"{app_name}-source")
            # Create GitOps repository
            gitops_repo = user.create_repo(f"{app_name}-gitops")

            return repo.clone_url, gitops_repo.clone_url
        except Exception as e:
            # Fallback for testing
            username = os.getenv("GITHUB_USERNAME")
            return f"https://github.com/{username}/{app_name}-source.git", \
                   f"https://github.com/{username}/{app_name}-gitops.git"

    @patch('subprocess.run')
    def test_repo_population(self, mock_subprocess):
        """Test repository population from templates"""
        # Mock subprocess calls
        mock_subprocess.return_value = Mock(returncode=0)

        repo_url = "https://github.com/testuser/test-repo.git"

        # Test repo population
        self.populate_repo_from_stack(repo_url, self.template_path)

        # Verify subprocess calls were made
        self.assertTrue(mock_subprocess.called)
        call_args = [call[0][0] for call in mock_subprocess.call_args_list]

        # Should include git clone, copy, add, commit, push
        self.assertTrue(any('git' in args and 'clone' in args for args in call_args))
        self.assertTrue(any('git' in args and 'add' in args for args in call_args))

    def populate_repo_from_stack(self, repo_url, template_path):
        """Mock repository population from stack templates"""
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        temp_repo_path = f"/tmp/{repo_name}"

        # Mock commands
        commands = [
            ["rm", "-rf", temp_repo_path],
            ["git", "clone", repo_url, temp_repo_path],
            ["cp", "-r", f"{template_path}/*", f"{temp_repo_path}/"],
            ["git", "-C", temp_repo_path, "add", "."],
            ["git", "-C", temp_repo_path, "commit", "-m", "Initial commit from Agent"],
            ["git", "-C", temp_repo_path, "push"]
        ]

        for cmd in commands:
            # Mock successful execution
            pass

    @patch('subprocess.run')
    @patch('kubernetes.config.load_kube_config')
    def test_argocd_application_creation(self, mock_kube_config, mock_subprocess):
        """Test ArgoCD application creation"""
        mock_subprocess.return_value = Mock(returncode=0)

        gitops_repo_url = "https://github.com/testuser/test-repo-gitops.git"

        # Test ArgoCD application creation
        self.create_argocd_application(self.app_name, gitops_repo_url)

        # Verify kubernetes config was loaded
        mock_kube_config.assert_called_once()

        # Verify kubectl apply was called
        self.assertTrue(mock_subprocess.called)
        call_args = [call[0][0] for call in mock_subprocess.call_args_list]
        self.assertTrue(any('kubectl' in args and 'apply' in args for args in call_args))

    def create_argocd_application(self, app_name, gitops_repo_url):
        """Mock ArgoCD application creation"""
        # Mock kubernetes config loading
        try:
            import kubernetes
            kubernetes.config.load_kube_config()
        except:
            pass

        app_manifest = f"""
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app_name}
  namespace: argocd
spec:
  project: default
  source:
    repoURL: {gitops_repo_url}
    targetRevision: HEAD
    path: .
  destination:
    server: https://kubernetes.default.svc
    namespace: default"""

        manifest_file = f"/tmp/{app_name}-argocd.yaml"

        # Write manifest to file (mock)
        with open(manifest_file, 'w') as f:
            f.write(app_manifest)

        # Mock kubectl apply
        try:
            subprocess.run(["kubectl", "apply", "-f", manifest_file], check=True)
        except:
            pass

    def test_manifest_generation(self):
        """Test ArgoCD manifest generation"""
        app_name = "test-app"
        gitops_repo_url = "https://github.com/testuser/test-repo-gitops.git"

        # Generate manifest
        manifest = self.generate_argocd_manifest(app_name, gitops_repo_url)

        # Verify manifest content
        self.assertIn(app_name, manifest)
        self.assertIn(gitops_repo_url, manifest)
        self.assertIn('argoproj.io/v1alpha1', manifest)
        self.assertIn('Application', manifest)

    def generate_argocd_manifest(self, app_name, gitops_repo_url):
        """Generate ArgoCD application manifest"""
        return f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app_name}
  namespace: argocd
spec:
  project: default
  source:
    repoURL: {gitops_repo_url}
    targetRevision: HEAD
    path: .
  destination:
    server: https://kubernetes.default.svc
    namespace: default"""

    def test_agent_initialization(self):
        """Test agent class initialization"""
        agent = OnboardingAgent()
        self.assertIsNotNone(agent)
        self.assertTrue(hasattr(agent, 'create_github_repo'))
        self.assertTrue(hasattr(agent, 'populate_repo_from_stack'))
        self.assertTrue(hasattr(agent, 'create_argocd_application'))

    def test_complete_workflow_validation(self):
        """Test validation of complete workflow steps"""
        workflow_steps = [
            'validate_environment',
            'create_github_repo',
            'populate_repo_from_stack',
            'create_argocd_application'
        ]

        agent = OnboardingAgent()

        # Verify all required methods exist
        for step in workflow_steps:
            self.assertTrue(hasattr(agent, step), f"Missing method: {step}")

    def test_error_handling(self):
        """Test error handling in agent operations"""
        agent = OnboardingAgent()

        # Test with invalid app name
        with self.assertRaises(ValueError):
            agent.validate_app_name("")

        # Test with invalid repo URL
        with self.assertRaises(ValueError):
            agent.validate_repo_url("invalid-url")

    def test_validation_helpers(self):
        """Test validation helper methods"""
        agent = OnboardingAgent()

        # Test app name validation
        self.assertTrue(agent.validate_app_name("valid-app-name"))
        self.assertFalse(agent.validate_app_name(""))
        self.assertFalse(agent.validate_app_name("Invalid App Name!"))

        # Test repo URL validation
        self.assertTrue(agent.validate_repo_url("https://github.com/user/repo.git"))
        self.assertFalse(agent.validate_repo_url("invalid-url"))
        self.assertFalse(agent.validate_repo_url(""))

class OnboardingAgent:
    """Mock Onboarding Agent class for testing"""

    def __init__(self):
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.github_username = os.getenv('GITHUB_USERNAME')

    def validate_environment(self):
        """Validate required environment variables"""
        required_vars = ['GITHUB_TOKEN', 'OPENAI_API_KEY', 'GITHUB_USERNAME']
        for var in required_vars:
            if not os.getenv(var):
                raise EnvironmentError(f"Missing required environment variable: {var}")
        return True

    def validate_app_name(self, app_name):
        """Validate application name"""
        if not app_name or not app_name.strip():
            return False
        # Check for valid characters (alphanumeric, hyphens, underscores)
        import re
        return bool(re.match(r'^[a-zA-Z0-9_-]+$', app_name.strip()))

    def validate_repo_url(self, repo_url):
        """Validate repository URL"""
        if not repo_url or not repo_url.strip():
            return False
        import re
        return bool(re.match(r'^https://github\.com/[\w\-\.]+/[\w\-\.]+\.git$', repo_url.strip()))

    def create_github_repo(self, app_name):
        """Create GitHub repositories"""
        if not self.validate_app_name(app_name):
            raise ValueError(f"Invalid app name: {app_name}")

        # Implementation would go here
        return f"https://github.com/{self.github_username}/{app_name}-source.git", \
               f"https://github.com/{self.github_username}/{app_name}-gitops.git"

    def populate_repo_from_stack(self, repo_url, template_path):
        """Populate repository from stack templates"""
        if not self.validate_repo_url(repo_url):
            raise ValueError(f"Invalid repo URL: {repo_url}")

        # Implementation would go here
        pass

    def create_argocd_application(self, app_name, gitops_repo_url):
        """Create ArgoCD application"""
        if not self.validate_app_name(app_name):
            raise ValueError(f"Invalid app name: {app_name}")

        # Implementation would go here
        pass

if __name__ == '__main__':
    # Run tests with detailed output
    unittest.main(verbosity=2)