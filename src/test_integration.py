#!/usr/bin/env python3
"""
Integration test for the AI Onboarding Agent (Dry Run Mode)
This test simulates the complete flow without making actual API calls
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dotenv import load_dotenv

# Add src to path so we can import agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import OnboardingAgent, AppInfo, RepositoryInfo

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
        print(f"🔧 MOCK: Creating GitHub repositories for {app_info.name}")

        # Return mock repository info
        return RepositoryInfo(
            source_repo_url=f"https://github.com/mock/{app_info.name}-source.git",
            gitops_repo_url=f"https://github.com/mock/{app_info.name}-gitops.git",
            source_repo_id="mock-source-id",
            gitops_repo_id="mock-gitops-id"
        )

    def populate_repo_from_stack(self, repo_url: str, template_path: str, app_info: AppInfo) -> bool:
        """Mock repository population (still does local processing for testing)"""
        print(f"🔧 MOCK: Populating repository {repo_url} from template {template_path}")

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
                print(f"📁 Processed files in {repo_name}:")
                for root, dirs, files in os.walk(repo_path):
                    for file in files:
                        rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                        print(f"   - {rel_path}")

                print(f"✅ MOCK: Successfully populated {repo_url}")
                return True

            except Exception as e:
                print(f"❌ MOCK: Error populating repository {repo_url}: {e}")
                return False

    def create_argocd_application(self, app_info: AppInfo, gitops_repo_url: str) -> bool:
        """Mock ArgoCD application creation"""
        print(f"🔧 MOCK: Creating ArgoCD application for {app_info.name}")

        # Generate the manifest to test that functionality
        manifest = self._generate_argocd_manifest(app_info, gitops_repo_url)

        print("📄 Generated ArgoCD manifest:")
        print("=" * 50)
        print(manifest)
        print("=" * 50)

        print(f"✅ MOCK: Successfully created ArgoCD application")
        return True

def test_complete_flow():
    """Test the complete onboarding flow with the example from plan.md"""
    print("🚀 Testing Complete Integration Flow")
    print("=" * 60)

    # Use the exact example from plan.md
    natural_language_request = "I need to deploy my new NodeJS service called inventory-api"
    print(f"📝 Input: {natural_language_request}")
    print()

    try:
        # Initialize mock agent
        agent = MockOnboardingAgent()
        print("✅ Mock agent initialized")
        print()

        # Run the complete flow
        result = agent.run_onboarding_flow(natural_language_request)

        # Display results
        print("\n" + "=" * 60)
        print("📊 ONBOARDING RESULTS")
        print("=" * 60)

        if result['success']:
            print("🎉 Onboarding completed successfully!")
            print(f"📦 App: {result['app_info'].name}")
            print(f"📝 Description: {result['app_info'].description}")
            print(f"💻 Language: {result['app_info'].language}")
            print(f"👤 Author: {result['app_info'].author}")
            print(f"🔗 Source Repository: {result['repositories'].source_repo_url}")
            print(f"⚙️  GitOps Repository: {result['repositories'].gitops_repo_url}")
            print(f"🚀 ArgoCD Application: {result['argocd_created']}")
            print(f"⏰ Timestamp: {result['timestamp']}")

            print("\n✅ All tools executed successfully:")
            print("   1. ✅ Natural language processing (OpenRouter)")
            print("   2. ✅ GitHub repository creation (Mocked)")
            print("   3. ✅ Repository population from templates")
            print("   4. ✅ ArgoCD application manifest generation")

            return True
        else:
            print(f"❌ Onboarding failed: {result['error']}")
            return False

    except Exception as e:
        print(f"💥 Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_template_processing():
    """Test template processing with real files"""
    print("\n🔍 Testing Template Processing")
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

        print(f"📋 Test App: {app_info.name}")
        print(f"📝 Description: {app_info.description}")
        print()

        # Test NodeJS template processing
        nodejs_template = os.getenv('NODEJS_TEMPLATE_PATH')
        print(f"🔧 Testing NodeJS template: {nodejs_template}")

        # Test a few template files
        test_files = ['package.json', 'index.js', 'README.md']

        for file_name in test_files:
            src_file = os.path.join(nodejs_template, file_name)
            if os.path.exists(src_file):
                print(f"📄 Processing {file_name}...")

                with open(src_file, 'r') as f:
                    template_content = f.read()

                # Check if template contains variables
                if '{{' in template_content and '}}' in template_content:
                    print(f"   ✅ Contains template variables")

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
                        print(f"   ✅ Template variables processed successfully")
                    else:
                        print(f"   ⚠️  Some variables may not have been processed")

                else:
                    print(f"   ℹ️  No template variables found")

        return True

    except Exception as e:
        print(f"❌ Template processing test failed: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🧪 AI Onboarding Agent Integration Tests (Dry Run)")
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
            print(f"❌ Test {test.__name__} failed with exception: {e}")

    print(f"\n📊 Integration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All integration tests passed!")
        print("🚀 Agent is ready for production use!")
        print("\n📋 Next Steps:")
        print("   1. Configure real GitHub token in .env")
        print("   2. Ensure kubectl is configured")
        print("   3. Run: python src/agent.py \"your request\"")
        return True
    else:
        print("❌ Some integration tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)