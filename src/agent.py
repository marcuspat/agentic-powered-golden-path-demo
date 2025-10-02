#!/usr/bin/env python3
"""
AI-Powered Developer Onboarding Agent

This agent automates the creation of GitHub repositories, populates them with
standardized templates, and deploys them to Kubernetes via GitOps using ArgoCD.

Features:
- Natural language processing with OpenRouter LLM
- GitHub repository creation and management
- Template-based repository population
- ArgoCD application deployment
- Comprehensive error handling and logging
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

import requests
from github import Github, GithubException
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from jinja2 import Environment, FileSystemLoader, Template
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class AppInfo:
    """Application information extracted from natural language"""
    name: str
    description: str
    language: str = "NodeJS"
    author: str = "AI Agent"
    repository_url: str = ""

@dataclass
class RepositoryInfo:
    """Repository creation result"""
    source_repo_url: str
    gitops_repo_url: str
    source_repo_id: str
    gitops_repo_id: str

class OnboardingAgent:
    """AI-Powered Developer Onboarding Agent"""

    def __init__(self):
        """Initialize the agent with configuration"""
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.openrouter_model = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3-sonnet')
        self.nodejs_template_path = os.getenv('NODEJS_TEMPLATE_PATH')
        self.gitops_template_path = os.getenv('GITOPS_TEMPLATE_PATH')
        self.argocd_namespace = os.getenv('ARGOCD_NAMESPACE', 'argocd')
        self.argocd_project = os.getenv('ARGOCD_PROJECT', 'default')

        # Validate required configuration
        self._validate_config()

        # Initialize GitHub client
        self.github = Github(self.github_token)

        # Load templates
        self.jinja_env = Environment(loader=FileSystemLoader('.'))

        logger.info("OnboardingAgent initialized successfully")

    def _validate_config(self):
        """Validate required configuration"""
        required_vars = [
            'GITHUB_TOKEN', 'GITHUB_USERNAME', 'OPENROUTER_API_KEY',
            'NODEJS_TEMPLATE_PATH', 'GITOPS_TEMPLATE_PATH'
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")

        # Validate template paths exist
        if not os.path.exists(self.nodejs_template_path):
            raise ValueError(f"NodeJS template path does not exist: {self.nodejs_template_path}")
        if not os.path.exists(self.gitops_template_path):
            raise ValueError(f"GitOps template path does not exist: {self.gitops_template_path}")

    def extract_app_info(self, natural_language_request: str) -> AppInfo:
        """
        Extract application information from natural language using OpenRouter

        Args:
            natural_language_request: Developer's request in natural language

        Returns:
            AppInfo object with extracted information
        """
        logger.info(f"Extracting app info from: {natural_language_request}")

        prompt = f"""
        Extract application information from this developer request: "{natural_language_request}"

        Return a JSON object with:
        - name: application name (lowercase, hyphenated)
        - description: brief description of what this application does
        - language: programming language (default to "NodeJS" if not specified)
        - author: developer name (default to "AI Agent" if not specified)

        Examples:
        Input: "I need to deploy my new NodeJS service called inventory-api"
        Output: {{"name": "inventory-api", "description": "NodeJS service for inventory management", "language": "NodeJS", "author": "AI Agent"}}

        Input: "Create a React frontend called user-dashboard"
        Output: {{"name": "user-dashboard", "description": "React frontend for user dashboard", "language": "React", "author": "AI Agent"}}

        Now process this request: "{natural_language_request}"

        Respond only with valid JSON, no additional text.
        """

        try:
            response = self._call_openrouter_api(prompt)
            app_data = json.loads(response.strip())

            return AppInfo(
                name=app_data.get('name', 'new-app'),
                description=app_data.get('description', 'New application created by AI agent'),
                language=app_data.get('language', 'NodeJS'),
                author=app_data.get('author', 'AI Agent')
            )

        except Exception as e:
            logger.error(f"Error extracting app info: {e}")
            # Fallback extraction logic
            return self._fallback_extraction(natural_language_request)

    def _call_openrouter_api(self, prompt: str) -> str:
        """Make API call to OpenRouter"""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.openrouter_model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 500
        }

        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            return result['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API error: {e}")
            raise

    def _fallback_extraction(self, request: str) -> AppInfo:
        """Fallback extraction logic when LLM fails"""
        logger.warning("Using fallback extraction logic")

        # Simple pattern matching for common patterns
        request_lower = request.lower()

        # Look for "called X" or "named X" patterns
        import re
        name_patterns = [
            r'called\s+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'named\s+["\']?([a-zA-Z0-9\-_]+)["\']?',
            r'["\']([a-zA-Z0-9\-_]+)["\']',
        ]

        app_name = "new-app"
        for pattern in name_patterns:
            match = re.search(pattern, request_lower)
            if match:
                app_name = match.group(1)
                break

        # Generate description from request
        description = f"Application created from request: {request[:100]}..."

        return AppInfo(
            name=app_name,
            description=description,
            language="NodeJS",
            author="AI Agent"
        )

    def create_github_repo(self, app_info: AppInfo) -> RepositoryInfo:
        """
        Create paired GitHub repositories (source and gitops)

        Args:
            app_info: Application information

        Returns:
            RepositoryInfo with repository URLs and IDs
        """
        logger.info(f"Creating GitHub repositories for {app_info.name}")

        try:
            user = self.github.get_user()

            # Create source repository
            source_repo_name = f"{app_info.name}-source"
            source_repo = user.create_repo(
                name=source_repo_name,
                description=f"Source code for {app_info.description}",
                private=False,
                auto_init=True,
                readme=f"# {app_info.name}\n\n{app_info.description}"
            )
            logger.info(f"Created source repo: {source_repo.html_url}")

            # Create GitOps repository
            gitops_repo_name = f"{app_info.name}-gitops"
            gitops_repo = user.create_repo(
                name=gitops_repo_name,
                description=f"GitOps configuration for {app_info.description}",
                private=False,
                auto_init=True,
                readme=f"# {app_info.name} GitOps\n\nArgoCD configuration for {app_info.description}"
            )
            logger.info(f"Created GitOps repo: {gitops_repo.html_url}")

            return RepositoryInfo(
                source_repo_url=source_repo.clone_url,
                gitops_repo_url=gitops_repo.clone_url,
                source_repo_id=str(source_repo.id),
                gitops_repo_id=str(gitops_repo.id)
            )

        except GithubException as e:
            logger.error(f"GitHub API error: {e}")
            if e.status == 422:
                # Repository already exists, try to get existing repos
                logger.info("Repository may already exist, attempting to use existing repos")
                return self._get_existing_repositories(app_info.name)
            raise

    def _get_existing_repositories(self, app_name: str) -> RepositoryInfo:
        """Get existing repositories if they already exist"""
        try:
            user = self.github.get_user()

            source_repo_name = f"{app_name}-source"
            gitops_repo_name = f"{app_name}-gitops"

            source_repo = user.get_repo(source_repo_name)
            gitops_repo = user.get_repo(gitops_repo_name)

            logger.info(f"Using existing repos: {source_repo.html_url}, {gitops_repo.html_url}")

            return RepositoryInfo(
                source_repo_url=source_repo.clone_url,
                gitops_repo_url=gitops_repo.clone_url,
                source_repo_id=str(source_repo.id),
                gitops_repo_id=str(gitops_repo.id)
            )

        except GithubException as e:
            logger.error(f"Cannot get existing repositories: {e}")
            # Fallback to constructed URLs
            username = self.github_username
            return RepositoryInfo(
                source_repo_url=f"https://github.com/{username}/{app_name}-source.git",
                gitops_repo_url=f"https://github.com/{username}/{app_name}-gitops.git",
                source_repo_id="unknown",
                gitops_repo_id="unknown"
            )

    def populate_repo_from_stack(self, repo_url: str, template_path: str, app_info: AppInfo) -> bool:
        """
        Clone a repository and populate it from a template

        Args:
            repo_url: Repository URL to clone and populate
            template_path: Path to template directory
            app_info: Application information for template substitution

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Populating repository {repo_url} from template {template_path}")

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Clone repository
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                repo_path = os.path.join(temp_dir, repo_name)

                logger.info(f"Cloning {repo_url} to {repo_path}")
                subprocess.run([
                    'git', 'clone', repo_url, repo_path
                ], check=True, capture_output=True, text=True)

                # Copy template files
                self._copy_template_files(template_path, repo_path, app_info)

                # Commit and push changes
                self._commit_and_push(repo_path, app_info)

                logger.info(f"Successfully populated {repo_url}")
                return True

            except subprocess.CalledProcessError as e:
                logger.error(f"Error populating repository {repo_url}: {e}")
                logger.error(f"stdout: {e.stdout}")
                logger.error(f"stderr: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error populating repository {repo_url}: {e}")
                return False

    def _copy_template_files(self, template_path: str, repo_path: str, app_info: AppInfo):
        """Copy and process template files"""
        # Set up Jinja2 environment for the template
        env = Environment(loader=FileSystemLoader(template_path))

        for root, dirs, files in os.walk(template_path):
            # Create corresponding directories in repo
            rel_path = os.path.relpath(root, template_path)
            if rel_path != '.':
                dest_dir = os.path.join(repo_path, rel_path)
                os.makedirs(dest_dir, exist_ok=True)

            # Process files
            for file in files:
                src_file = os.path.join(root, file)

                if rel_path == '.':
                    dest_file = os.path.join(repo_path, file)
                else:
                    dest_file = os.path.join(repo_path, rel_path, file)

                # Check if file should be processed as template
                if self._should_process_as_template(file):
                    self._process_template_file(src_file, dest_file, env, app_info)
                else:
                    # Copy file as-is
                    shutil.copy2(src_file, dest_file)

    def _should_process_as_template(self, filename: str) -> bool:
        """Check if file should be processed as Jinja2 template"""
        template_extensions = ['.js', '.json', '.md', '.yaml', '.yml', '.env.example']
        return any(filename.endswith(ext) for ext in template_extensions)

    def _process_template_file(self, src_file: str, dest_file: str, env: Environment, app_info: AppInfo):
        """Process a single template file"""
        try:
            with open(src_file, 'r') as f:
                template_content = f.read()

            template = env.from_string(template_content)
            rendered_content = template.render(
                appName=app_info.name,
                description=app_info.description,
                language=app_info.language,
                author=app_info.author,
                repositoryUrl=f"https://github.com/{self.github_username}/{app_info.name}-source",
                imageName=f"{self.github_username}/{app_info.name}",
                imageTag="latest",
                ingressHost=f"{app_info.name}.local"
            )

            with open(dest_file, 'w') as f:
                f.write(rendered_content)

        except Exception as e:
            logger.error(f"Error processing template file {src_file}: {e}")
            # Copy original file as fallback
            shutil.copy2(src_file, dest_file)

    def _commit_and_push(self, repo_path: str, app_info: AppInfo):
        """Commit and push changes to repository"""
        # Configure git user
        subprocess.run(['git', '-C', repo_path, 'config', 'user.name', 'AI Onboarding Agent'], check=True)
        subprocess.run(['git', '-C', repo_path, 'config', 'user.email', 'agent@example.com'], check=True)

        # Add all changes
        subprocess.run(['git', '-C', repo_path, 'add', '.'], check=True)

        # Commit changes
        commit_message = f"Initial commit for {app_info.name}\n\n{app_info.description}"
        subprocess.run(['git', '-C', repo_path, 'commit', '-m', commit_message], check=True)

        # Push changes
        subprocess.run(['git', '-C', repo_path, 'push'], check=True)

    def create_argocd_application(self, app_info: AppInfo, gitops_repo_url: str) -> bool:
        """
        Create ArgoCD Application manifest and apply it to Kubernetes

        Args:
            app_info: Application information
            gitops_repo_url: GitOps repository URL

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Creating ArgoCD application for {app_info.name}")

        try:
            # Load Kubernetes configuration
            config.load_kube_config()

            # Create ArgoCD application manifest
            app_manifest = self._generate_argocd_manifest(app_info, gitops_repo_url)

            # Apply the manifest
            return self._apply_kubernetes_manifest(app_manifest, app_info.name)

        except Exception as e:
            logger.error(f"Error creating ArgoCD application: {e}")
            return False

    def _generate_argocd_manifest(self, app_info: AppInfo, gitops_repo_url: str) -> str:
        """Generate ArgoCD Application manifest"""
        manifest = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app_info.name}
  namespace: {self.argocd_namespace}
  labels:
    app: {app_info.name}
    created-by: ai-onboarding-agent
spec:
  project: {self.argocd_project}
  source:
    repoURL: {gitops_repo_url}
    targetRevision: HEAD
    path: .
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
    - PrunePropagationPolicy=foreground
    - PruneLast=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
  ignoreDifferences:
  - group: apps
    kind: Deployment
    jsonPointers:
    - /spec/replicas"""

        return manifest

    def _apply_kubernetes_manifest(self, manifest: str, app_name: str) -> bool:
        """Apply Kubernetes manifest"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest)
            manifest_file = f.name

        try:
            # Apply manifest using kubectl
            result = subprocess.run([
                'kubectl', 'apply', '-f', manifest_file
            ], capture_output=True, text=True, check=True)

            logger.info(f"ArgoCD application created: {result.stdout.strip()}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Error applying ArgoCD manifest: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            return False
        finally:
            os.unlink(manifest_file)

    def run_onboarding_flow(self, natural_language_request: str) -> Dict[str, Any]:
        """
        Run the complete onboarding flow

        Args:
            natural_language_request: Developer's request in natural language

        Returns:
            Dictionary with onboarding results
        """
        logger.info(f"Starting onboarding flow for request: {natural_language_request}")

        result = {
            'success': False,
            'app_info': None,
            'repositories': None,
            'argocd_created': False,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }

        try:
            # Step 1: Extract application information
            app_info = self.extract_app_info(natural_language_request)
            result['app_info'] = app_info
            logger.info(f"Extracted app info: {app_info}")

            # Step 2: Create GitHub repositories
            repo_info = self.create_github_repo(app_info)
            result['repositories'] = repo_info
            logger.info(f"Created repositories: {repo_info}")

            # Step 3: Populate source repository
            source_success = self.populate_repo_from_stack(
                repo_info.source_repo_url,
                self.nodejs_template_path,
                app_info
            )
            if not source_success:
                raise Exception("Failed to populate source repository")

            # Step 4: Populate GitOps repository
            gitops_success = self.populate_repo_from_stack(
                repo_info.gitops_repo_url,
                self.gitops_template_path,
                app_info
            )
            if not gitops_success:
                raise Exception("Failed to populate GitOps repository")

            # Step 5: Create ArgoCD application
            argocd_success = self.create_argocd_application(app_info, repo_info.gitops_repo_url)
            result['argocd_created'] = argocd_success

            result['success'] = True
            logger.info(f"Onboarding flow completed successfully for {app_info.name}")

            return result

        except Exception as e:
            logger.error(f"Onboarding flow failed: {e}")
            result['error'] = str(e)
            return result

def main():
    """Main function to run the agent"""
    # Check configuration
    if len(sys.argv) < 2:
        print("Usage: python agent.py \"<natural language request>\"")
        print("Example: python agent.py \"I need to deploy my new NodeJS service called inventory-api\"")
        sys.exit(1)

    natural_language_request = sys.argv[1]

    try:
        # Initialize and run agent
        agent = OnboardingAgent()
        result = agent.run_onboarding_flow(natural_language_request)

        # Print results
        if result['success']:
            print("\n🎉 Onboarding completed successfully!")
            print(f"📦 App: {result['app_info'].name}")
            print(f"📝 Description: {result['app_info'].description}")
            print(f"🔗 Source Repository: {result['repositories'].source_repo_url}")
            print(f"⚙️  GitOps Repository: {result['repositories'].gitops_repo_url}")
            print(f"🚀 ArgoCD Application: {result['argocd_created']}")
            print(f"\n📊 Check ArgoCD UI for deployment status")
        else:
            print(f"\n❌ Onboarding failed: {result['error']}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        print(f"\n💥 Agent execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()