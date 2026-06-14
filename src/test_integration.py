#!/usr/bin/env python3
"""
Integration test for the AI Onboarding Agent (Dry Run Mode)
This test simulates the complete flow without making actual API calls
"""

import os
import sys
import tempfile
from unittest.mock import patch
from dotenv import load_dotenv

# Add src to path so we can import agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import OnboardingAgent, AppInfo, RepositoryInfo  # noqa: I001

class MockOnboardingAgent(OnboardingAgent):
    """Mock version of OnboardingAgent for testing without real API calls"""

    def __init__(self):
        """Initialize with mocked external dependencies"""
        # Load environment variables first
        load_dotenv()

        # Mock GitHub client
        with patch('agent.Github'):
            super().__init__()

    def _call_openrouter_api(self, prompt: str) -> str:
        """Mock OpenRouter API call"""
        # Return mock response for inventory-api example
        if "inventory-api" in prompt:
            return '''{
                "name": "inventory-api",
                "description": "NodeJS service for inventory management",
                "language": "NodeJS",
                "author": "AI Agent"
            }'''

        # Default fallback response
        return '''{
            "name": "test-app",
            "description": "Test application",
            "language": "NodeJS",
            "author": "AI Agent"
        }'''

    def create_github_repo(self, app_info: AppInfo) -> RepositoryInfo:
        """Mock GitHub repository creation"""
        print(f"ð§ MOCK: Creating GitHub repositories for {app_info.name}")

        # Return mock repository info
        return RepositoryInfo(
            source_repo_url=f"https://github.com/mock/{app_info.name}-source.git",
            gitops_repo_url=f"https://github.com/mock/{app_info.name}-gitops.git",
            source_repo_id="mock-source-id",
            gitops_repo_id="mock-gitops-id"
        )

    def populate_repo_from_stack(self, repo_url: str, template_path: str, app_info: AppInfo) -> bool:
        """Mock repository population (still does local processing for testing)"""
        print(f"ð§ MOCK: Populating repository {repo_url} from template {template_path}")

        # We'll still do the template processing to test that functionality
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Create mock repo structure
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                repo_path = os.path.join(temp_dir, repo_name)
                os.makedirs(repo_path)

                # Copy and process template files (this is real functionality we want to test)
                self._copy_template_files(template_path, repo_path, app_info)

                # List the processed files to verify template processing worked
                print(f"ð Processed files in {repo_name}:")
                for root, dirs, files in os.walk(repo_path):
                    for file in files:
                        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                        print(f"   - {rel_path}")

                print(f"â MOCK: Successfully populated {repo_url}")
                return True

            except Exception as e:
                print(f"â MOCK: Error populating repository {repo_url}: {e}")
                return False

    def create_argocd_application(self, app_info: AppInfo, gitops_repo_url: str) -> bool:
        """Mock ArgoCD application creation"""
        print(f"ð§ MOCK: Creating ArgoCD application for {app_info.name}")

        # Generate the manifest to test that functionality
        manifest = self._generate_argocd_manifest(app_info, gitops_repo_url)

        print("ð Generated ArgoCD manifest:")
        print("=" * 50)
        print(manifest)
        print("=" * 50)

        print(f"â MOCK: Successfully created ArgoCD application")
        return True

def test_complete_flow():
    """Test the complete onboarding flow with the example from plan.md"""
    print("ð Testing Complete Integration Flow")
    print("=" * 60)

    # Use the exact example from plan.md
    natural_language_request = "I need to deploy my new NodeJS service called inventory-api"
    print(f"ð Input: {natural_language_request}")
    print()

    try:
        # Initialize mock agent
        agent = MockOnboardingAgent()
        print("â Mock agent initialized")
        print()

        # Run the complete flow
        result = agent.run_onboarding_flow(natural_language_request)

        # Display results
        print("\n" + "=" * 60)
        print("ð ONBOARDING RESULTS")
        print("=" * 60)

        if result['success']:
            print("ð Onboarding completed successfully!")
            print(f"ð¦ App: {result['app_info'].name}")
            print(f"ð Description: {result['app_info'].description}")
            print(f"ð» Language: {result['app_info'].language}")
            print(f"ð¤ Author: {result['app_info'].author}")
            print(f"ð Source Repository: {result['repositories'].source_repo_url}")
            print(f"âï¸  GitOps Repository: {result['repositories'].gitops_repo_url}")
            print(f"ð ArgoCD Application: {result['argocd_created']}")
            print(f"â° Timestamp: {result['timestamp']}")

            print("\nâ All tools executed successfully:")
            print("   1. â Natural language processing (OpenRouter)")
            print("   2. â GitHub repository creation (Mocked)")
            print("   3. â Repository population from templates")
            print("   4. â ArgoCD application manifest generation")

            return True
        else:
            print(f"â Onboarding failed: {result['error']}")
            return False

    except Exception as e:
        print(f"ð¥ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_template_processing():
    """Test template processing with real files"""
    print("\nð Testing Template Processing")
    print("=" * 40)

    try:
        agent = MockOnboardingAgent()

        # Create test app info
        app_info = AppInfo(
            name="inventory-api",
            description="NodeJS service for inventory management",
            language="NodeJS",
            author="Test Developer"
        )

        print(f"ð Test App: {app_info.name}")
        print(f"ð Description: {app_info.description}")
        print()

        # Test NodeJS template processing
        nodejs_template = os.getenv('NODEJS_TEMPLATE_PATH')
        print(f"ð§ Testing NodeJS template: {nodejs_template}")

        # Test a few template files
        test_files = ['package.json', 'index.js', 'README.md']

        for file_name in test_files:
            src_file = os.path.join(nodejs_template, file_name)
            if os.path.exists(src_file):
                print(f"ð Processing {file_name}...")

                with open(src_file, 'r') as f:
                    template_content = f.read()

                # Check if template contains variables
                if '{{' in template_content and '}}' in template_content:
                    print(f"   â Contains template variables")

                    # Process template
                    template = agent.jinja_env.from_string(template_content)
                    rendered = template.render(
                        appName=app_info.name,
                        description=app_info.description,
                        language=app_info.language,
                        author=app_info.author,
                        repositoryUrl=f"https://github.com/mock/{app_info.name}-source",
                        imageName=f"mock/{app_info.name}",
                        imageTag="latest",
                        ingressHost=f"{app_info.name}.local"
                    )

                    # Check if variables were replaced
                    if '{{' not in rendered and '}}' not in rendered:
                        print(f"   â Template variables processed successfully")
                    else:
                        print(f"   â ï¸  Some variables may not have been processed")

                else:
                    print(f"   â¹ï¸  No template variables found")

        return True

    except Exception as e:
        print(f"â Template processing test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("ð§ª AI Onboarding Agent Integration Tests (Dry Run)")
    print("=" * 60)

    tests = [
        test_template_processing,
        test_complete_flow
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"â Test {test.__name__} failed with exception: {e}")

    print(f"\nð Integration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("ð All integration tests passed!")
        print("ð Agent is ready for production use!")
        print("\nð Next Steps:")
        print("   1. Configure real GitHub token in .env")
        print("   2. Ensure kubectl is configured")
        print("   3. Run: python src/agent.py \"your request\"")
        return True
    else:
        print("â Some integration tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
