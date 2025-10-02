#!/usr/bin/env python3
"""
Test script for the AI Onboarding Agent
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add src to path so we can import agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import OnboardingAgent, AppInfo

def test_environment_setup():
    """Test that required environment variables are accessible"""
    print("🔍 Testing environment setup...")

    required_vars = [
        'GITHUB_TOKEN', 'GITHUB_USERNAME', 'OPENROUTER_API_KEY',
        'NODEJS_TEMPLATE_PATH', 'GITOPS_TEMPLATE_PATH'
    ]

    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
        else:
            print(f"✅ {var}: {'*' * min(len(value), 10)}")

    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        return False

    print("✅ Environment setup complete")
    return True

def test_template_paths():
    """Test that template paths exist"""
    print("\n🔍 Testing template paths...")

    nodejs_template = os.getenv('NODEJS_TEMPLATE_PATH')
    gitops_template = os.getenv('GITOPS_TEMPLATE_PATH')

    if not os.path.exists(nodejs_template):
        print(f"❌ NodeJS template path doesn't exist: {nodejs_template}")
        return False

    if not os.path.exists(gitops_template):
        print(f"❌ GitOps template path doesn't exist: {gitops_template}")
        return False

    print(f"✅ NodeJS template: {nodejs_template}")
    print(f"✅ GitOps template: {gitops_template}")
    return True

def test_agent_initialization():
    """Test that agent can be initialized"""
    print("\n🔍 Testing agent initialization...")

    try:
        agent = OnboardingAgent()
        print("✅ Agent initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        return False

def test_template_processing():
    """Test template file processing"""
    print("\n🔍 Testing template processing...")

    try:
        agent = OnboardingAgent()

        # Create test app info
        app_info = AppInfo(
            name="test-app",
            description="Test application for template processing",
            language="NodeJS",
            author="Test Agent"
        )

        # Test Jinja2 template rendering
        test_template = "Hello {{appName}}!"
        template = agent.jinja_env.from_string(test_template)
        result = template.render(appName=app_info.name)

        expected = "Hello test-app!"
        if result == expected:
            print("✅ Template processing works")
            return True
        else:
            print(f"❌ Template processing failed: expected '{expected}', got '{result}'")
            return False

    except Exception as e:
        print(f"❌ Template processing test failed: {e}")
        return False

def test_fallback_extraction():
    """Test fallback extraction logic"""
    print("\n🔍 Testing fallback extraction...")

    try:
        agent = OnboardingAgent()

        # Test various input patterns
        test_cases = [
            "I need to deploy my new NodeJS service called inventory-api",
            "Create a React app called user-dashboard",
            "Build a backend service named payment-processor",
            "Simple app"
        ]

        expected_results = [
            "inventory-api",
            "user-dashboard",
            "payment-processor",
            "new-app"
        ]

        all_passed = True
        for i, (test_input, expected) in enumerate(zip(test_cases, expected_results)):
            result = agent._fallback_extraction(test_input)
            if result.name == expected:
                print(f"✅ Test case {i+1}: '{test_input}' -> '{result.name}'")
            else:
                print(f"❌ Test case {i+1}: '{test_input}' -> '{result.name}' (expected '{expected}')")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"❌ Fallback extraction test failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("🚀 Running AI Onboarding Agent Tests\n")

    tests = [
        test_environment_setup,
        test_template_paths,
        test_agent_initialization,
        test_template_processing,
        test_fallback_extraction
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Agent is ready for use.")
        return True
    else:
        print("❌ Some tests failed. Please check configuration.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)