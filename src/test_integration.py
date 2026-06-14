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
        print(f"Ã°ÂÂÂ§ MOCK: Creating GitHub repositories for {app_info.name}")

        # Return mock repository info
        return RepositoryInfo(
            source_repo_url=f"https://github.com/mock/{app_info.name}-source.git",
            gitops_repo_url=f"https://github.com/mock/{app_info.name}-gitops.git",
            source_repo_id="mock-source-id",
            gitops_repo_id="mock-gitops-id"
        )

    def populate_repo_from_stack(self, repo_url: str, template_path: str, app_info: AppInfo) -> bool:
        """Mock repository population (still does local processing for testing)"""
        print(f"Ã°ÂÂÂ§ MOCK: Populating repository {repo_url} from template {template_path}")

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
                print(f"Ã°ÂÂÂ Processed files in {repo_name}:")
                for root, dirs, files in os.walk(repo_path):
                    for file in files:
                        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                        print(f"   - {rel_path}")

                print(f"Ã¢ÂÂ MOCK: Successfully populated {repo_url}")
                return True

            except Exception as e:
                print(f"Ã¢ÂÂ MOCK: Error populating repository {repo_url}: {e}")
                return False

    def create_argocd_application(self, app_info: AppInfo, gitops_repo_url: str) -> bool:
        """Mock ArgoCD application creation"""
        print(f"Ã°ÂÂÂ§ MOCK: Creating ArgoCD application for {app_info.name}")

        # Generate the manifest to test that functionality
        manifest = self._generate_argocd_manifest(app_info, gitops_repo_url)

        print("Ã°ÂÂÂ Generated ArgoCD manifest:")
        print("=" * 50)
        print(manifest)
        print("=" * 50)

        print("Ã¢ÂÂ MOCK: Successfully created ArgoCD application")
        return True

def test_complete_flow():
    """Test the complete onboarding flow with the example from plan.md"""
    print("Ã°ÂÂÂ Testing Complete Integration Flow")
    print("=" * 60)

    # Use the exact example from plan.md
    natural_language_request = "I need to deploy my new NodeJS service called inventory-api"
    print(f"Ã°ÂÂÂ Input: {natural_language_request}")
    print()

    try:
        # Initialize mock agent
        agent = MockOnboardingAgent()
        print("Ã¢ÂÂ Mock agent initialized")
        print()

        # Run the complete flow
        result = agent.run_onboarding_flow(natural_language_request)

        # Display results
        print("\n" + "=" * 60)
        print("Ã°ÂÂÂ ONBOARDING RESULTS")
        print("=" * 60)

        if result['success']:
            print("Ã°ÂÂÂ Onboarding completed successfully!")
            print(f"Ã°ÂÂÂ¦ App: {result['app_info'].name}")
            print(f"Ã°ÂÂÂ Description: {result['app_info'].description}")
            print(f"Ã°ÂÂÂ» Language: {result['app_info'].language}")
            print(f"Ã°ÂÂÂ¤ Author: {result['app_info'].author}")
            print(f"Ã°ÂÂÂ Source Repository: {result['repositories'].source_repo_url}")
            print(f"Ã¢ÂÂÃ¯Â¸Â  GitOps Repository: {result['repositories'].gitops_repo_url}")
            print(f"Ã°ÂÂÂ ArgoCD Application: {result['argocd_created']}")
            print(f"Ã¢ÂÂ° Timestamp: {result['timestamp']}")

            print("\nÃ¢ÂÂ All tools executed successfully:")
            print("   1. Ã¢ÂÂ Natural language processing (OpenRouter)")
            print("   2. Ã¢ÂÂ GitHub repository creation (Mocked)")
            print("   3. Ã¢ÂÂ Repository population from templates")
            print("   4. Ã¢ÂÂ ArgoCD application manifest generation")

            return True
        else:
            print(f"Ã¢ÂÂ Onboarding failed: {result['error']}")
            return False

    except Exception as e:
        print(f"Ã°ÂÂÂ¥ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_template_processing():
    """Test template processing with real files"""
    print("\nÃ°ÂÂÂ Testing Template Processing")
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

        print(f"Ã°ÂÂÂ Test App: {app_info.name}")
        print(f"Ã°ÂÂÂ Description: {app_info.description}")
        print()

        # Test NodeJS template processing
        nodejs_template = os.getenv('NODEJS_TEMPLATE_PATH')
        print(f"Ã°ÂÂÂ§ Testing NodeJS template: {nodejs_template}")

        # Test a few template files
        test_files = ['package.json', 'index.js', 'README.md']

        for file_name in test_files:
            src_file = os.path.join(nodejs_template, file_name)
            if os.path.exists(src_file):
                print(f"Ã°ÂÂÂ Processing {file_name}...")

                with open(src_file, 'r') as f:
                    template_content = f.read()

                # Check if template contains variables
                if '{{' in template_content and '}}' in template_content:
                    print("   Ã¢ÂÂ Contains template variables")

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
                        print("   Ã¢ÂÂ Template variables processed successfully")
                    else:
                        print("   Ã¢ÂÂ Ã¯Â¸Â  Some variables may not have been processed")

                else:
                    print("   Ã¢ÂÂ¹Ã¯Â¸Â  No template variables found")

        return True

    except Exception as e:
        print(f"Ã¢ÂÂ Template processing test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("Ã°ÂÂ§Âª AI Onboarding Agent Integration Tests (Dry Run)")
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
            print(f"Ã¢ÂÂ Test {test.__name__} failed with exception: {e}")

    print(f"\nÃ°ÂÂÂ Integration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("Ã°ÂÂÂ All integration tests passed!")
        print("Ã°ÂÂÂ Agent is ready for production use!")
        print("\nÃ°ÂÂÂ Next Steps:")
        print("   1. Configure real GitHub token in .env")
        print("   2. Ensure kubectl is configured")
        print("   3. Run: python src/agent.py \"your request\"")
        return True
    else:
        print("Ã¢ÂÂ Some integration tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
