import os
import subprocess
import json
import re
from github import Github
from kubernetes import client, config
from jinja2 import Template
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Tool 1: Create GitHub Repo ---
def create_github_repo(app_name):
    logger.info(f"Tool: Creating GitHub repo for {app_name}...")

    g = Github(os.getenv("GITHUB_TOKEN"))
    user = g.get_user()

    try:
        # Create source repository
        source_repo = user.create_repo(f"{app_name}-source",
                                     description=f"Source code for {app_name}",
                                     private=False,
                                     auto_init=True)

        # Create GitOps repository
        gitops_repo = user.create_repo(f"{app_name}-gitops",
                                     description=f"GitOps configuration for {app_name}",
                                     private=False,
                                     auto_init=True)

        logger.info(f"Successfully created repos: {source_repo.clone_url}, {gitops_repo.clone_url}")
        return source_repo.clone_url, gitops_repo.clone_url

    except Exception as e:
        logger.warning(f"Error creating repos: {e}")
        # Fallback for existing repos
        username = os.getenv("GITHUB_USERNAME")
        return f"https://github.com/{username}/{app_name}-source.git", f"https://github.com/{username}/{app_name}-gitops.git"

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

            # Ensure target directory exists
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            # Read template file
            with open(template_file, 'r') as f:
                content = f.read()

            # Substitute template variables
            template = Template(content)
            rendered_content = template.render(appName=app_name, description=description)

            # Write to target
            with open(target_path, 'w') as f:
                f.write(rendered_content)

    # Commit and push changes
    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "add", "."], check=True)
    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "commit", "-m", "Initial commit from Golden Path Agent"], check=True)
    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "push"], check=True)

    logger.info("Successfully populated and pushed to repo.")
    return True

# --- Tool 3: Deploy via GitOps (ArgoCD) ---
def create_argocd_application(app_name, gitops_repo_url):
    logger.info(f"Tool: Creating ArgoCD Application for {app_name}...")

    # Load kube config
    config.load_kube_config()

    # Create ArgoCD Application manifest
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

    # Apply the manifest to the cluster
    try:
        subprocess.run(["kubectl", "apply", "-f", manifest_file], check=True)
        logger.info("Successfully applied ArgoCD Application manifest.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error applying manifest: {e}")
        return False

# --- Natural Language Processing ---
def extract_app_name_from_request(request):
    """Extract app name from natural language request using OpenRouter API"""
    try:
        import openai

        client = openai.OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )

        prompt = f"""
        Extract the application name from this developer request: "{request}"

        Return only the application name in lowercase with hyphens, no other text.
        Examples:
        - "I need a new NodeJS service called inventory-api" -> "inventory-api"
        - "Deploy my user-management service" -> "user-management"
        - "Create a payment-processor app" -> "payment-processor"
        """

        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            temperature=0.1
        )

        app_name = response.choices[0].message.content.strip().lower()

        # Clean up response
        app_name = re.sub(r'[^a-z0-9-]', '', app_name)
        app_name = re.sub(r'-+', '-', app_name).strip('-')

        if app_name:
            return app_name

    except Exception as e:
        logger.warning(f"AI extraction failed: {e}")

    # Fallback: Simple pattern matching
    patterns = [
        r'called\s+([a-zA-Z0-9-]+)',
        r'named\s+([a-zA-Z0-9-]+)',
        r'([a-zA-Z0-9-]+)\s+service',
        r'([a-zA-Z0-9-]+)\s+app',
        r'deploy\s+([a-zA-Z0-9-]+)',
        r'create\s+([a-zA-Z0-9-]+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, request, re.IGNORECASE)
        if match:
            return match.group(1).lower()

    # Default fallback
    return "my-app"

# --- Main Agent Logic ---
def run_onboarding_flow(developer_request):
    logger.info(f"--- Starting Onboarding for request: '{developer_request}' ---")

    # Extract app name from natural language
    app_name = extract_app_name_from_request(developer_request)
    logger.info(f"Extracted app name: {app_name}")

    # 1. Create repos
    source_repo_url, gitops_repo_url = create_github_repo(app_name)
    logger.info(f"Created repos: {source_repo_url}, {gitops_repo_url}")

    # 2. Populate them from our local stack templates
    template_path = os.path.join(os.getcwd(), "..", "cnoe-stacks", "nodejs-template", "app-source")
    gitops_template_path = os.path.join(os.getcwd(), "..", "cnoe-stacks", "nodejs-gitops-template")

    # Populate source repo
    if not populate_repo_from_stack(source_repo_url, template_path, app_name, f"NodeJS application for {app_name}"):
        logger.error("Failed to populate source repository")
        return False

    # Populate GitOps repo
    if not populate_repo_from_stack(gitops_repo_url, gitops_template_path, app_name, f"GitOps configuration for {app_name}"):
        logger.error("Failed to populate GitOps repository")
        return False

    # 3. Tell ArgoCD to deploy the app
    if not create_argocd_application(app_name, gitops_repo_url):
        logger.error("Failed to create ArgoCD application")
        return False

    logger.info(f"--- Onboarding for '{app_name}' Complete! ---")
    logger.info(f"ArgoCD is now deploying your application.")
    logger.info(f"Access ArgoCD: https://cnoe.localtest.me/argocd")
    logger.info(f"App will be available at: http://{app_name}.cnoe.localtest.me")

    return True

if __name__ == "__main__":
    # Check required environment variables
    required_vars = ["GITHUB_TOKEN", "GITHUB_USERNAME", "OPENROUTER_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        exit(1)

    # Get developer request from command line argument or use default
    import sys
    developer_request = sys.argv[1] if len(sys.argv) > 1 else "I need to deploy my new NodeJS service called inventory-api"

    # Run the onboarding flow
    success = run_onboarding_flow(developer_request)

    if success:
        logger.info("✅ Golden Path onboarding completed successfully!")
        exit(0)
    else:
        logger.error("❌ Golden Path onboarding failed!")
        exit(1)