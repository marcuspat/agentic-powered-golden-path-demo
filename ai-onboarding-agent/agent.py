"""
DEPRECATED: This module is the v1 functional-style agent.
The production implementation is in src/agent.py (OOP, type-annotated, --dry-run support).
This file is kept for backward compatibility with existing demo scripts.
"""

import logging
import os
import re
import subprocess

from github import Github
from jinja2 import Template
from kubernetes import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Stop-words that appear after "deploy"/"create" but are NOT app names
_REGEX_STOP_WORDS = {
    'my', 'a', 'an', 'the', 'new', 'some', 'any', 'this', 'that',
    'something', 'anything', 'everything', 'nothing', 'it', 'them',
    'generic', 'service', 'app', 'application', 'project',
}


# --- Tool 1: Create GitHub Repo ---
def create_github_repo(app_name):
    logger.info(f"Tool: Creating GitHub repo for {app_name}...")

    # FIX: wrap the entire GitHub interaction (including get_user) in try/except
    try:
        g = Github(os.getenv("GITHUB_TOKEN"))
        user = g.get_user()

        # Create source repository
        source_repo = user.create_repo(
            f"{app_name}-source",
            description=f"Source code for {app_name}",
            private=False,
            auto_init=True,
        )

        # Create GitOps repository
        gitops_repo = user.create_repo(
            f"{app_name}-gitops",
            description=f"GitOps configuration for {app_name}",
            private=False,
            auto_init=True,
        )

        logger.info(f"Successfully created repos: {source_repo.clone_url}, {gitops_repo.clone_url}")
        return source_repo.clone_url, gitops_repo.clone_url

    except Exception as e:
        logger.warning(f"Error creating repos: {e}")
        # Fallback: construct URLs from env
        username = os.getenv("GITHUB_USERNAME")
        return (
            f"https://github.com/{username}/{app_name}-source.git",
            f"https://github.com/{username}/{app_name}-gitops.git",
        )


# --- Tool 2: Populate Repo from Stack ---
def populate_repo_from_stack(repo_url, template_path, app_name, description=""):
    logger.info(f"Tool: Populating {repo_url} from {template_path}...")

    repo_name = repo_url.split('/')[-1].replace('.git', '')

    # Clean up any existing repo
    subprocess.run(["rm", "-rf", f"/tmp/{repo_name}"], check=False)

    # Clone the repository
    subprocess.run(["git", "clone", repo_url, f"/tmp/{repo_name}"], check=True)

    # Check if template path exists
    if not os.path.exists(template_path):
        logger.error(f"Template path does not exist: {template_path}")
        return False

    # Copy template files and substitute variables
    for root, dirs, files in os.walk(template_path):
        for file in files:
            template_file = os.path.join(root, file)
            relative_path = os.path.relpath(template_file, template_path)
            target_path = f"/tmp/{repo_name}/{relative_path}"

            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            with open(template_file, 'r') as f:
                content = f.read()

            template = Template(content)
            rendered_content = template.render(appName=app_name, description=description)

            with open(target_path, 'w') as f:
                f.write(rendered_content)

    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "add", "."], check=True)
    subprocess.run(
        ["git", "-C", f"/tmp/{repo_name}", "commit", "-m", "Initial commit from Golden Path Agent"],
        check=True,
    )
    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "push"], check=True)

    logger.info("Successfully populated and pushed to repo.")
    return True


# --- Tool 3: Deploy via GitOps (ArgoCD) ---
def create_argocd_application(app_name, gitops_repo_url):
    logger.info(f"Tool: Creating ArgoCD Application for {app_name}...")

    config.load_kube_config()

    app_manifest = f"""apiVersion: argoproj.io/v1alpha1
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
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
"""

    manifest_file = f"/tmp/{app_name}-argocd.yaml"
    with open(manifest_file, "w") as f:
        f.write(app_manifest)

    # FIX: catch generic Exception, not just CalledProcessError
    try:
        subprocess.run(["kubectl", "apply", "-f", manifest_file], check=True)
        logger.info("Successfully applied ArgoCD Application manifest.")
        return True
    except Exception as e:
        logger.error(f"Error applying manifest: {e}")
        return False


# --- Natural Language Processing ---
def extract_app_name_from_request(request):
    """Extract app name from natural language request using OpenRouter API"""
    try:
        import openai

        ai_client = openai.OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )

        prompt = f"""
        Extract the application name from this developer request: "{request}"

        Return only the application name in lowercase with hyphens, no other text.
        Examples:
        - "I need a new NodeJS service called inventory-api" -> "inventory-api"
        - "Deploy my user-management service" -> "user-management"
        - "Create a payment-processor app" -> "payment-processor"
        """

        response = ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1,
        )

        app_name = response.choices[0].message.content.strip().lower()
        app_name = re.sub(r'[^a-z0-9-]', '', app_name)
        app_name = re.sub(r'-+', '-', app_name).strip('-')

        if app_name:
            return app_name

    except Exception as e:
        logger.warning(f"AI extraction failed: {e}")

    # Fallback: pattern matching Ã¢ÂÂ ordered from most to least specific.
    # Key insight: intended app names are always hyphenated identifiers;
    # stop-words and English words are not.
    patterns = [
        # 1. Explicit "called X" or "named X" Ã¢ÂÂ highest confidence
        r'(?:called|named)\s+["\']?([a-zA-Z0-9][a-zA-Z0-9-]+)["\']?',
        # 2. Hyphenated identifier immediately before a service/app keyword
        r'([a-zA-Z0-9][a-zA-Z0-9-]+-[a-zA-Z0-9-]+)\s+(?:service|app|application)',
        # 3. Any hyphenated identifier anywhere in the request
        #    (catches "Deploy order-service", "I need to create auth-service")
        r'\b([a-zA-Z0-9][a-zA-Z0-9-]+-[a-zA-Z0-9-]+)\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, request, re.IGNORECASE)
        if match:
            candidate = match.group(1).lower()
            # FIX: reject stop-words Ã¢ÂÂ they're not app names
            if candidate not in _REGEX_STOP_WORDS:
                return candidate

    return "my-app"


# --- Main Agent Logic ---
def run_onboarding_flow(developer_request):
    logger.info(f"--- Starting Onboarding for request: '{developer_request}' ---")

    app_name = extract_app_name_from_request(developer_request)
    logger.info(f"Extracted app name: {app_name}")

    source_repo_url, gitops_repo_url = create_github_repo(app_name)
    logger.info(f"Created repos: {source_repo_url}, {gitops_repo_url}")

    template_path = os.path.join(os.getcwd(), "..", "cnoe-stacks", "nodejs-template", "app-source")
    gitops_template_path = os.path.join(os.getcwd(), "..", "cnoe-stacks", "nodejs-gitops-template")

    if not populate_repo_from_stack(source_repo_url, template_path, app_name, f"NodeJS application for {app_name}"):
        logger.error("Failed to populate source repository")
        return False

    if not populate_repo_from_stack(gitops_repo_url, gitops_template_path, app_name, f"GitOps configuration for {app_name}"):
        logger.error("Failed to populate GitOps repository")
        return False

    if not create_argocd_application(app_name, gitops_repo_url):
        logger.error("Failed to create ArgoCD application")
        return False

    logger.info(f"--- Onboarding for '{app_name}' Complete! ---")
    logger.info("ArgoCD is now deploying your application.")
    logger.info("Access ArgoCD: https://cnoe.localtest.me/argocd")
    logger.info(f"App will be available at: http://{app_name}.cnoe.localtest.me")

    return True


if __name__ == "__main__":
    required_vars = ["GITHUB_TOKEN", "GITHUB_USERNAME", "OPENROUTER_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)

    import sys
    developer_request = sys.argv[1] if len(sys.argv) > 1 else "I need to deploy my new NodeJS service called inventory-api"

    success = run_onboarding_flow(developer_request)

    if success:
        logger.info("Ã¢ÂÂ Golden Path onboarding completed successfully!")
        exit(0)
    else:
        logger.error("Ã¢ÂÂ Golden Path onboarding failed!")
        exit(1)
