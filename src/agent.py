#!/usr/bin/env python3
"""
AI-Powered Developer Onboarding Agent

Automates GitHub repo creation, Jinja2 template population, and ArgoCD deployment
from a single natural-language developer request.

Usage:
    python agent.py "I need to deploy my new NodeJS service called inventory-api"
    python agent.py --dry-run "Deploy a payment-processor service"
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

import requests
from dotenv import load_dotenv
from github import Github, GithubException
from jinja2 import Environment, FileSystemLoader
from kubernetes import client

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AppInfo:
    """Application information extracted from natural language."""
    name: str
    description: str
    language: str = "NodeJS"
    author: str = "AI Agent"
    repository_url: str = ""


@dataclass
class RepositoryInfo:
    """Repository creation result."""
    source_repo_url: str
    gitops_repo_url: str
    source_repo_id: str
    gitops_repo_id: str


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class OnboardingAgent:
    """AI-Powered Developer Onboarding Agent."""

    def __init__(self, dry_run: bool = False):
        """
        Initialise the agent.

        Args:
            dry_run: When True, skip all external side-effects (GitHub, kubectl).
                     Prints what *would* happen instead.
        """
        self.dry_run = dry_run

        self.github_token = os.getenv('GITHUB_TOKEN')
        self.github_username = os.getenv('GITHUB_USERNAME')
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        self.openrouter_model = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3-sonnet')
        self.nodejs_template_path = os.getenv('NODEJS_TEMPLATE_PATH', '')
        self.gitops_template_path = os.getenv('GITOPS_TEMPLATE_PATH', '')
        self.argocd_namespace = os.getenv('ARGOCD_NAMESPACE', 'argocd')
        self.argocd_project = os.getenv('ARGOCD_PROJECT', 'default')

        if not dry_run:
            self._validate_config()
            self.github = Github(self.github_token)
        else:
            logger.info("[DRY-RUN] Skipping config validation and GitHub auth")
            self.github = None

        self.jinja_env = Environment(loader=FileSystemLoader('.'))
        logger.info(f"OnboardingAgent initialised (dry_run={dry_run})")

    # ------------------------------------------------------------------
    # Config / validation
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate required env vars and template paths."""
        required_vars = [
            'GITHUB_TOKEN', 'GITHUB_USERNAME', 'OPENROUTER_API_KEY',
            'NODEJS_TEMPLATE_PATH', 'GITOPS_TEMPLATE_PATH',
        ]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            raise ValueError(f"Missing required environment variables: {missing}")

        for label, path in [
            ('NODEJS_TEMPLATE_PATH', self.nodejs_template_path),
            ('GITOPS_TEMPLATE_PATH', self.gitops_template_path),
        ]:
            if path and not os.path.exists(path):
                raise ValueError(f"{label} does not exist: {path}")

    # ------------------------------------------------------------------
    # NLP extraction
    # ------------------------------------------------------------------

    def extract_app_info(self, request: str) -> AppInfo:
        """Extract AppInfo from a natural-language developer request."""
        logger.info(f"Extracting app info from: {request}")

        prompt = f"""
Extract application information from this developer request: "{request}"

Return a JSON object with:
- name: application name (lowercase, hyphenated)
- description: brief description of what this application does
- language: programming language (default "NodeJS" if not specified)
- author: developer name (default "AI Agent" if not specified)

Respond only with valid JSON, no additional text.
"""
        try:
            response = self._call_openrouter_api(prompt)
            app_data = json.loads(response.strip())
            return AppInfo(
                name=app_data.get('name', 'new-app'),
                description=app_data.get('description', 'New application'),
                language=app_data.get('language', 'NodeJS'),
                author=app_data.get('author', 'AI Agent'),
            )
        except Exception as e:
            logger.warning(f"LLM extraction failed ({e}), using fallback")
            return self._fallback_extraction(request)

    def _call_openrouter_api(self, prompt: str) -> str:
        """POST to OpenRouter chat completions."""
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.openrouter_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    def _fallback_extraction(self, request: str) -> AppInfo:
        """Pattern-match fallback when LLM is unavailable."""
        import re
        logger.warning("Using regex fallback for app name extraction")

        patterns = [
            r'(?:called|named)\s+["\']?([a-zA-Z0-9][a-zA-Z0-9-]+)["\']?',
            r'([a-zA-Z0-9][a-zA-Z0-9-]+-[a-zA-Z0-9-]+)\s+(?:service|app|application)',
            r'\b([a-zA-Z0-9][a-zA-Z0-9-]+-[a-zA-Z0-9-]+)\b',
        ]

        stop_words = {
            'my', 'a', 'an', 'the', 'new', 'some', 'any', 'this', 'that',
            'something', 'anything', 'everything', 'nothing', 'it',
        }

        for pattern in patterns:
            match = re.search(pattern, request, re.IGNORECASE)
            if match:
                candidate = match.group(1).lower()
                if candidate not in stop_words:
                    return AppInfo(name=candidate, description=f"Application: {candidate}")

        return AppInfo(name="new-app", description=f"Application from: {request[:80]}")

    # ------------------------------------------------------------------
    # GitHub
    # ------------------------------------------------------------------

    def create_github_repo(self, app_info: AppInfo) -> RepositoryInfo:
        """Create paired source + gitops repositories."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create: {app_info.name}-source, {app_info.name}-gitops")
            return RepositoryInfo(
                source_repo_url=f"https://github.com/DRY-RUN/{app_info.name}-source.git",
                gitops_repo_url=f"https://github.com/DRY-RUN/{app_info.name}-gitops.git",
                source_repo_id="dry-run",
                gitops_repo_id="dry-run",
            )

        logger.info(f"Creating GitHub repositories for {app_info.name}")
        try:
            user = self.github.get_user()

            source_repo = user.create_repo(
                name=f"{app_info.name}-source",
                description=f"Source code for {app_info.description}",
                private=False,
                auto_init=True,
            )
            gitops_repo = user.create_repo(
                name=f"{app_info.name}-gitops",
                description=f"GitOps config for {app_info.description}",
                private=False,
                auto_init=True,
            )
            logger.info(f"Created: {source_repo.html_url}, {gitops_repo.html_url}")
            return RepositoryInfo(
                source_repo_url=source_repo.clone_url,
                gitops_repo_url=gitops_repo.clone_url,
                source_repo_id=str(source_repo.id),
                gitops_repo_id=str(gitops_repo.id),
            )

        except GithubException as e:
            if e.status == 422:
                logger.info("Repos may already exist Ã¢ÂÂ retrieving existing")
                return self._get_existing_repositories(app_info.name)
            raise

    def _get_existing_repositories(self, app_name: str) -> RepositoryInfo:
        """Fall back to existing repos if creation returns 422."""
        try:
            user = self.github.get_user()
            source = user.get_repo(f"{app_name}-source")
            gitops = user.get_repo(f"{app_name}-gitops")
            return RepositoryInfo(
                source_repo_url=source.clone_url,
                gitops_repo_url=gitops.clone_url,
                source_repo_id=str(source.id),
                gitops_repo_id=str(gitops.id),
            )
        except GithubException as e:
            logger.error(f"Cannot retrieve existing repos: {e}")
            return RepositoryInfo(
                source_repo_url=f"https://github.com/{self.github_username}/{app_name}-source.git",
                gitops_repo_url=f"https://github.com/{self.github_username}/{app_name}-gitops.git",
                source_repo_id="unknown",
                gitops_repo_id="unknown",
            )

    # ------------------------------------------------------------------
    # Template population
    # ------------------------------------------------------------------

    def populate_repo_from_stack(
        self, repo_url: str, template_path: str, app_info: AppInfo
    ) -> bool:
        """Clone repo_url and populate from Jinja2 template_path."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would populate {repo_url} from {template_path}")
            return True

        logger.info(f"Populating {repo_url} from {template_path}")

        with tempfile.TemporaryDirectory() as tmp:
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            repo_path = os.path.join(tmp, repo_name)

            try:
                subprocess.run(
                    ['git', 'clone', repo_url, repo_path],
                    check=True, capture_output=True, text=True,
                )
                self._copy_template_files(template_path, repo_path, app_info)
                self._commit_and_push(repo_path, app_info)
                logger.info(f"Successfully populated {repo_url}")
                return True

            except subprocess.CalledProcessError as e:
                logger.error(f"Git error populating {repo_url}: {e.stderr}")
                return False
            except Exception as e:
                logger.error(f"Error populating {repo_url}: {e}")
                return False

    def _copy_template_files(
        self, template_path: str, repo_path: str, app_info: AppInfo
    ) -> None:
        """Walk template_path, render Jinja2 vars, write to repo_path."""
        template_extensions = {'.js', '.json', '.md', '.yaml', '.yml', '.env.example'}

        for root, _, files in os.walk(template_path):
            rel_dir = os.path.relpath(root, template_path)
            dest_dir = repo_path if rel_dir == '.' else os.path.join(repo_path, rel_dir)
            os.makedirs(dest_dir, exist_ok=True)

            for fname in files:
                src = os.path.join(root, fname)
                dest = os.path.join(dest_dir, fname)

                if any(fname.endswith(ext) for ext in template_extensions):
                    try:
                        with open(src) as f:
                            rendered = Environment().from_string(f.read()).render(
                                appName=app_info.name,
                                description=app_info.description,
                                language=app_info.language,
                                author=app_info.author,
                                imageName=f"{self.github_username}/{app_info.name}",
                                imageTag="latest",
                                ingressHost=f"{app_info.name}.cnoe.localtest.me",
                            )
                        with open(dest, 'w') as f:
                            f.write(rendered)
                    except Exception as e:
                        logger.warning(f"Template render failed for {src}: {e} Ã¢ÂÂ copying as-is")
                        shutil.copy2(src, dest)
                else:
                    shutil.copy2(src, dest)

    def _commit_and_push(self, repo_path: str, app_info: AppInfo) -> None:
        """Stage, commit, and push all changes."""
        for cmd in [
            ['git', '-C', repo_path, 'config', 'user.name', 'AI Onboarding Agent'],
            ['git', '-C', repo_path, 'config', 'user.email', 'agent@golden-path.local'],
            ['git', '-C', repo_path, 'add', '.'],
            ['git', '-C', repo_path, 'commit', '-m',
             f"chore: golden-path init for {app_info.name}\n\n{app_info.description}"],
            ['git', '-C', repo_path, 'push'],
        ]:
            subprocess.run(cmd, check=True, capture_output=True, text=True)

    # ------------------------------------------------------------------
    # ArgoCD
    # ------------------------------------------------------------------

    def create_argocd_application(
        self, app_info: AppInfo, gitops_repo_url: str
    ) -> bool:
        """Generate and apply an ArgoCD Application manifest."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create ArgoCD Application '{app_info.name}'")
            logger.info(f"[DRY-RUN]   repoURL: {gitops_repo_url}")
            return True

        logger.info(f"Creating ArgoCD application for {app_info.name}")

        manifest = self._generate_argocd_manifest(app_info, gitops_repo_url)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(manifest)
            manifest_file = f.name

        try:
            result = subprocess.run(
                ['kubectl', 'apply', '-f', manifest_file],
                capture_output=True, text=True, check=True,
            )
            logger.info(f"ArgoCD application created: {result.stdout.strip()}")
            return True
        except Exception as e:
            logger.error(f"kubectl apply failed: {e}")
            return False
        finally:
            os.unlink(manifest_file)

    def _generate_argocd_manifest(self, app_info: AppInfo, gitops_repo_url: str) -> str:
        return f"""apiVersion: argoproj.io/v1alpha1
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
    - /spec/replicas
"""

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run_onboarding_flow(self, request: str) -> Dict[str, Any]:
        """
        Run the complete onboarding flow.

        Returns a result dict with keys:
            success, app_info, repositories, argocd_created, error, timestamp
        """
        logger.info(f"Starting onboarding flow: {request}")

        result: Dict[str, Any] = {
            'success': False,
            'app_info': None,
            'repositories': None,
            'argocd_created': False,
            'error': None,
            'timestamp': datetime.now().isoformat(),
            'dry_run': self.dry_run,
        }

        try:
            app_info = self.extract_app_info(request)
            result['app_info'] = app_info
            logger.info(f"App info: {app_info}")

            repo_info = self.create_github_repo(app_info)
            result['repositories'] = repo_info

            for label, url, path in [
                ('source', repo_info.source_repo_url, self.nodejs_template_path),
                ('gitops', repo_info.gitops_repo_url, self.gitops_template_path),
            ]:
                if not self.populate_repo_from_stack(url, path, app_info):
                    raise RuntimeError(f"Failed to populate {label} repository")

            result['argocd_created'] = self.create_argocd_application(
                app_info, repo_info.gitops_repo_url
            )
            result['success'] = True
            logger.info(f"Onboarding complete for {app_info.name}")

        except Exception as e:
            logger.error(f"Onboarding flow failed: {e}")
            result['error'] = str(e)

        return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="AI-Powered Developer Onboarding Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py "I need to deploy my new NodeJS service called inventory-api"
  python agent.py --dry-run "Deploy a payment-processor service"
  python agent.py --model openai/gpt-4o "Create an order-management service"
        """,
    )
    p.add_argument("request", help="Natural-language deployment request")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would happen without creating repos or touching Kubernetes",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Override OPENROUTER_MODEL env var",
    )
    return p


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.model:
        os.environ['OPENROUTER_MODEL'] = args.model

    try:
        agent = OnboardingAgent(dry_run=args.dry_run)
        result = agent.run_onboarding_flow(args.request)

        if result['success']:
            tag = "[DRY-RUN] " if args.dry_run else ""
            print(f"\n{tag}Ã°ÂÂÂ Onboarding completed successfully!")
            ai = result['app_info']
            repos = result['repositories']
            print(f"  Ã°ÂÂÂ¦ App:         {ai.name}")
            print(f"  Ã°ÂÂÂ Description: {ai.description}")
            print(f"  Ã°ÂÂÂ Source repo: {repos.source_repo_url}")
            print(f"  Ã¢ÂÂÃ¯Â¸Â  GitOps repo: {repos.gitops_repo_url}")
            print(f"  Ã°ÂÂÂ ArgoCD:      {result['argocd_created']}")
            if not args.dry_run:
                print(f"\n  Ã°ÂÂÂ App URL: http://{ai.name}.cnoe.localtest.me")
        else:
            print(f"\nÃ¢ÂÂ Onboarding failed: {result['error']}")
            return 1

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        print(f"\nÃ°ÂÂÂ¥ {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
