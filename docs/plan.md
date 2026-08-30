Project 1: The "Golden Path" AI-Powered Developer OnboardingObjective: To create an AI agent that takes a developer's request in natural language (e.g., "I need a new NodeJS service called 'inventory-api'") and automatically performs the entire initial setup: creating a Git repository, populating it with a standardized template, and deploying it to a development Kubernetes environment via GitOps.Core CNOE Repos Used:cnoe-io/idpbuilder: To bootstrap the Kubernetes-based Internal Developer Platform (IDP).cnoe-io/stacks: To define the "golden path" template for a NodeJS application.cnoe-io/ai-platform-engineering (Conceptually): To inform the design of the agent's "tools."PrerequisitesDocker Desktop (or another container runtime).kubectl and git installed on your local machine.A GitHub account and a Personal Access Token (PAT) with repo permissions.An OpenAI API Key (or another LLM provider's key).Python 3.9+ and pip installed.Architecture FlowDeveloper         AI Agent                GitHub                Kubernetes Cluster
(CLI/Chat)    (Python/LangChain)                                  (via idpbuilder)
    |                 |                      |                         |
1. "Deploy my app" -->|                      |                         |
    |                 |                      |                         |
    |            2. Create Repo API Call --> |                         |
    |                 |                      |                         |
    |                 |                 3. Push "Stack" Code --> |     |
    |                 |                      |                         |
    |            4. Generate & Apply ArgoCD Manifest --.             |
    |                 |                                |             |
    |                 |<-------------------------------'             |
    |<-- "Done!"      |                                          5. ArgoCD syncs repo
    |                 |                                          6. Tekton builds/deploys
    |                 |                                          7. App is live
Step-by-Step Implementation GuidePhase 1: Platform Setup with idpbuilderClone idpbuilder and run it: This will create a local KinD Kubernetes cluster with ArgoCD, Tekton, and other necessary components.git clone [https://github.com/cnoe-io/idpbuilder.git](https://github.com/cnoe-io/idpbuilder.git)
cd idpbuilder
./idpbuilder run
This process can take 15-20 minutes. Once complete, your ~/.kube/config will be updated to point to the new KinD cluster.Verify the installation: Check that pods are running in the cluster.kubectl get pods -A
Phase 2: Create the "Golden Path" StackCreate a local directory for your stack template. This will serve as the blueprint for new applications.mkdir -p cnoe-stacks/nodejs-template/app-source
cd cnoe-stacks/nodejs-template
Create a simple NodeJS application (app-source/index.js):const http = require('http');
const port = 8080;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello from our Golden Path App!\n');
});

server.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
Create Kubernetes manifests for deployment (deployment.yaml):# This will be used by the GitOps repo, not the app source repo.
# We will create a separate GitOps config repo template.
mkdir -p ../nodejs-gitops-template
cat <<EOF > ../nodejs-gitops-template/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{.Values.appName}}
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
        image: gcr.io/google-samples/hello-app:1.0 # In a real scenario, Tekton would build and push your image
        ports:
        - containerPort: 8080
EOF
Note: We've simplified here by using a pre-built image. A full solution would have a Tekton pipeline to build the app-source code.Phase 3: Develop the Onboarding AgentSet up your Python environment:mkdir ~/agentic-onboarding-agent && cd ~/agentic-onboarding-agent
python -m venv venv
source venv/bin/activate
pip install openai PyGithub kubernetes
Set environment variables:export GITHUB_TOKEN='your_github_pat'
export OPENAI_API_KEY='your_openai_key'
export GITHUB_USERNAME='your_github_username'
Create the agent script (agent.py):import os
import subprocess
import json
from github import Github
from kubernetes import client, config

# --- Tool 1: Create GitHub Repo ---
def create_github_repo(app_name):
    print(f"Tool: Creating GitHub repo for {app_name}...")
    g = Github(os.getenv("GITHUB_TOKEN"))
    user = g.get_user()
    try:
        repo = user.create_repo(f"{app_name}-source")
        gitops_repo = user.create_repo(f"{app_name}-gitops")
        print(f"Successfully created repos: {repo.clone_url}, {gitops_repo.clone_url}")
        return repo.clone_url, gitops_repo.clone_url
    except Exception as e:
        print(f"Error creating repo: {e}")
        # Fallback for existing repos
        username = os.getenv("GITHUB_USERNAME")
        return f"[https://github.com/](https://github.com/){username}/{app_name}-source.git", f"[https://github.com/](https://github.com/){username}/{app_name}-gitops.git"


# --- Tool 2: Populate Repo from Stack ---
def populate_repo_from_stack(repo_url, template_path):
    print(f"Tool: Populating {repo_url} from {template_path}...")
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    subprocess.run(["rm", "-rf", "/tmp/" + repo_name])
    subprocess.run(["git", "clone", repo_url, f"/tmp/{repo_name}"], check=True)
    subprocess.run(f"cp -r {template_path}/* /tmp/{repo_name}/", shell=True, check=True)

    # In a real agent, you'd substitute template values here

    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "add", "."], check=True)
    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "commit", "-m", "Initial commit from Agent"], check=True)
    subprocess.run(["git", "-C", f"/tmp/{repo_name}", "push"], check=True)
    print("Successfully populated and pushed to repo.")

# --- Tool 3: Deploy via GitOps (ArgoCD) ---
def create_argocd_application(app_name, gitops_repo_url):
    print(f"Tool: Creating ArgoCD Application for {app_name}...")
    config.load_kube_config()
    # This manifest creates an App in ArgoCD, telling it to watch the -gitops repo
    app_manifest = f"""
apiVersion: argoproj.io/v1alpha1kind: Applicationmetadata:name: {app_name}namespace: argocdspec:project: defaultsource:repoURL: {gitops_repo_url}targetRevision: HEADpath: .destination:server: https://kubernetes.default.svcnamespace: default"""manifest_file = f"/tmp/{app_name}-argocd.yaml"with open(manifest_file, "w") as f:f.write(app_manifest)    # Apply the manifest to the cluster
    try:
        subprocess.run(["kubectl", "apply", "-f", manifest_file], check=True)
        print("Successfully applied ArgoCD Application manifest.")
    except subprocess.CalledProcessError as e:
        print(f"Error applying manifest: {e}")


# --- Main Agent Logic ---
def run_onboarding_flow(app_name):
    print(f"--- Starting Onboarding for '{app_name}' ---")
    
    # 1. Create repos
    source_repo_url, gitops_repo_url = create_github_repo(app_name)
    
    # 2. Populate them from our local stack templates
    # NOTE: You must have the template paths correct on your local machine
    populate_repo_from_stack(source_repo_url, "/path/to/your/cnoe-stacks/nodejs-template")
    populate_repo_from_stack(gitops_repo_url, "/path/to/your/cnoe-stacks/nodejs-gitops-template")
    
    # 3. Tell ArgoCD to deploy the app
    create_argocd_application(app_name, gitops_repo_url)
    
    print(f"--- Onboarding for '{app_name}' Complete! ---")
    print(f"ArgoCD is now deploying your application. Check the ArgoCD UI.")


if __name__ == "__main__":
    # This simulates the input from a developer
    developer_request = "I need to deploy my new NodeJS service called inventory-api"
    
    # A simple LLM call could extract 'inventory-api' from the request
    # For this script, we'll hardcode it.
    app_name_to_deploy = "inventory-api"
    
    run_onboarding_flow(app_name_to_deploy)
```
Run the agent:Crucially, update the paths in the populate_repo_from_stack calls in the script to point to your actual local stack directories.python agent.py
How to DemonstrateStart recording your screen.Show the empty GitHub account (or one without the new repos).Show the empty 'default' namespace in Kubernetes (kubectl get all -n default).Run the agent.py script. Narrate what the agent is doing as its logs appear in the terminal.Show the newly created repositories in GitHub with the code populated.Open the ArgoCD UI (get the password and port-forward instructions from the idpbuilder output) and show the new inventory-api application tile appearing and syncing.Show the application pods, services, etc., being created in Kubernetes (kubectl get all -n default).Conclude by showing you can access the running service.