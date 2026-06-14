#!/usr/bin/env python3
"""
Test suite for src/agent.py ÃÂ¢ÃÂÃÂ OnboardingAgent (OOP / production implementation).

Run:
    PYTHONPATH=src pytest src/test_agent.py -v
    # or without pytest:
    python src/test_agent.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure src/ is on path when running directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _set_env(**kwargs):
    """Context-free env setter ÃÂ¢ÃÂÃÂ patches os.environ for the test."""
    for k, v in kwargs.items():
        os.environ[k] = v


def _make_agent(dry_run=True, **env_overrides):
    """Return an OnboardingAgent in dry-run mode (no real credentials needed)."""
    _set_env(
        GITHUB_TOKEN='test-token',
        GITHUB_USERNAME='test-user',
        OPENROUTER_API_KEY='test-key',
        NODEJS_TEMPLATE_PATH='/tmp',   # exists
        GITOPS_TEMPLATE_PATH='/tmp',   # exists
    )
    for k, v in env_overrides.items():
        os.environ[k] = v

    from agent import OnboardingAgent
    return OnboardingAgent(dry_run=dry_run)


# ---------------------------------------------------------------------------
# Tests: __init__ / config validation
# ---------------------------------------------------------------------------

class TestInit(unittest.TestCase):

    def test_dry_run_skips_validation(self):
        """dry_run=True should not raise even with missing env vars."""
        for var in ['GITHUB_TOKEN', 'GITHUB_USERNAME', 'OPENROUTER_API_KEY',
                    'NODEJS_TEMPLATE_PATH', 'GITOPS_TEMPLATE_PATH']:
            os.environ.pop(var, None)

        from agent import OnboardingAgent
        # Should not raise
        agent = OnboardingAgent(dry_run=True)
        self.assertTrue(agent.dry_run)
        self.assertIsNone(agent.github)

    def test_missing_env_raises_without_dry_run(self):
        """Missing required env vars should raise ValueError in live mode."""
        for var in ['GITHUB_TOKEN', 'GITHUB_USERNAME', 'OPENROUTER_API_KEY',
                    'NODEJS_TEMPLATE_PATH', 'GITOPS_TEMPLATE_PATH']:
            os.environ.pop(var, None)

        from agent import OnboardingAgent
        with self.assertRaises((ValueError, Exception)):
            OnboardingAgent(dry_run=False)

    def test_default_model_is_claude(self):
        agent = _make_agent()
        self.assertIn('claude', agent.openrouter_model.lower())

    def test_argocd_defaults(self):
        agent = _make_agent()
        self.assertEqual(agent.argocd_namespace, 'argocd')
        self.assertEqual(agent.argocd_project, 'default')


# ---------------------------------------------------------------------------
# Tests: extract_app_info / NLP
# ---------------------------------------------------------------------------

class TestExtractAppInfo(unittest.TestCase):

    def setUp(self):
        self.agent = _make_agent()

    def test_llm_path_returns_structured_info(self):
        """When OpenRouter returns valid JSON, use it."""
        payload = json.dumps({
            "name": "inventory-api",
            "description": "Inventory management service",
            "language": "NodeJS",
            "author": "AI Agent",
        })
        with patch.object(self.agent, '_call_openrouter_api', return_value=payload):
            info = self.agent.extract_app_info("Deploy inventory-api service")

        self.assertEqual(info.name, "inventory-api")
        self.assertEqual(info.description, "Inventory management service")
        self.assertEqual(info.language, "NodeJS")

    def test_llm_failure_triggers_fallback(self):
        """When OpenRouter throws, fallback should still return an AppInfo."""
        from agent import AppInfo
        with patch.object(self.agent, '_call_openrouter_api', side_effect=Exception("timeout")):
            info = self.agent.extract_app_info("I need a service called payment-processor")

        self.assertIsInstance(info, AppInfo)
        self.assertNotEqual(info.name, '')

    def test_fallback_called_pattern(self):
        """'called X' pattern should extract 'inventory-api'."""
        with patch.object(self.agent, '_call_openrouter_api', side_effect=Exception):
            info = self.agent.extract_app_info(
                "I need to deploy my new NodeJS service called inventory-api"
            )
        self.assertEqual(info.name, "inventory-api")

    def test_fallback_hyphenated_adjacent_to_service(self):
        """'payment-processor service' should match hyphenated pattern."""
        with patch.object(self.agent, '_call_openrouter_api', side_effect=Exception):
            info = self.agent.extract_app_info("Deploy my payment-processor service")
        self.assertEqual(info.name, "payment-processor")

    def test_fallback_default_when_nothing_matches(self):
        """Generic request with no identifiable name ÃÂ¢ÃÂÃÂ 'new-app'."""
        with patch.object(self.agent, '_call_openrouter_api', side_effect=Exception):
            info = self.agent.extract_app_info("Just deploy something generic")
        self.assertEqual(info.name, "new-app")

    def test_llm_returns_invalid_json_triggers_fallback(self):
        """Malformed JSON from LLM should fall through to regex."""
        with patch.object(self.agent, '_call_openrouter_api', return_value="not json {{{"):
            info = self.agent.extract_app_info("Service called order-service")
        self.assertIsNotNone(info.name)


# ---------------------------------------------------------------------------
# Tests: create_github_repo
# ---------------------------------------------------------------------------

class TestCreateGithubRepo(unittest.TestCase):

    def setUp(self):
        self.agent = _make_agent(dry_run=False)
        # Inject a mock github client
        self.mock_github = MagicMock()
        self.agent.github = self.mock_github

    def _app_info(self, name="inventory-api"):
        from agent import AppInfo
        return AppInfo(name=name, description="Test app")

    def test_creates_two_repos(self):
        mock_user = MagicMock()
        mock_source = MagicMock(clone_url="https://github.com/u/inventory-api-source.git", id=1)
        mock_gitops = MagicMock(clone_url="https://github.com/u/inventory-api-gitops.git", id=2)
        mock_user.create_repo.side_effect = [mock_source, mock_gitops]
        self.mock_github.get_user.return_value = mock_user

        result = self.agent.create_github_repo(self._app_info())

        self.assertEqual(mock_user.create_repo.call_count, 2)
        self.assertIn("inventory-api-source", result.source_repo_url)
        self.assertIn("inventory-api-gitops", result.gitops_repo_url)

    def test_422_falls_back_to_existing_repos(self):
        from github import GithubException

        mock_user = MagicMock()
        mock_user.create_repo.side_effect = GithubException(422, "already exists", {})

        mock_source = MagicMock(clone_url="https://github.com/u/inventory-api-source.git", id=1)
        mock_gitops = MagicMock(clone_url="https://github.com/u/inventory-api-gitops.git", id=2)
        mock_user.get_repo.side_effect = [mock_source, mock_gitops]
        self.mock_github.get_user.return_value = mock_user

        result = self.agent.create_github_repo(self._app_info())
        self.assertIn("source", result.source_repo_url)

    def test_dry_run_returns_stub_urls(self):
        agent = _make_agent(dry_run=True)
        from agent import AppInfo
        info = AppInfo(name="test-app", description="desc")
        result = agent.create_github_repo(info)

        self.assertIn("DRY-RUN", result.source_repo_url)
        self.assertIn("DRY-RUN", result.gitops_repo_url)
        self.assertEqual(result.source_repo_id, "dry-run")


# ---------------------------------------------------------------------------
# Tests: populate_repo_from_stack
# ---------------------------------------------------------------------------

class TestPopulateRepo(unittest.TestCase):

    def setUp(self):
        self.agent = _make_agent(dry_run=False)
        self.tmp = tempfile.mkdtemp()
        self.template_dir = os.path.join(self.tmp, "template")
        os.makedirs(self.template_dir)
        # Write a simple Jinja2 template
        with open(os.path.join(self.template_dir, "app.yaml"), "w") as f:
            f.write("name: {{appName}}\ndescription: {{description}}\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _app_info(self):
        from agent import AppInfo
        return AppInfo(name="test-app", description="A test app")

    def test_nonexistent_template_path_returns_false(self):
        result = self.agent.populate_repo_from_stack(
            "https://github.com/x/y.git", "/nonexistent/path", self._app_info()
        )
        self.assertFalse(result)

    def test_dry_run_returns_true_without_git(self):
        agent = _make_agent(dry_run=True)
        result = agent.populate_repo_from_stack(
            "https://github.com/x/y.git", "/nonexistent/path", self._app_info()
        )
        self.assertTrue(result)

    @patch('agent.subprocess.run')
    def test_git_failure_returns_false(self, mock_run):
        mock_run.side_effect = __import__('subprocess').CalledProcessError(
            1, 'git', stderr='auth failed'
        )
        result = self.agent.populate_repo_from_stack(
            "https://github.com/x/y.git", self.template_dir, self._app_info()
        )
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Tests: create_argocd_application
# ---------------------------------------------------------------------------

class TestCreateArgocdApplication(unittest.TestCase):

    def setUp(self):
        self.agent = _make_agent(dry_run=False)

    def _app_info(self, name="test-app"):
        from agent import AppInfo
        return AppInfo(name=name, description="desc")

    def test_dry_run_returns_true(self):
        agent = _make_agent(dry_run=True)
        result = agent.create_argocd_application(
            self._app_info(), "https://github.com/x/gitops.git"
        )
        self.assertTrue(result)

    @patch('agent.subprocess.run')
    def test_successful_kubectl_apply(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="created")
        result = self.agent.create_argocd_application(
            self._app_info(), "https://github.com/x/gitops.git"
        )
        self.assertTrue(result)
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:2], ['kubectl', 'apply'])

    @patch('agent.subprocess.run')
    def test_generic_exception_returns_false(self, mock_run):
        """Any exception from subprocess ÃÂ¢ÃÂÃÂ not just CalledProcessError ÃÂ¢ÃÂÃÂ must return False."""
        mock_run.side_effect = Exception("connection refused")
        result = self.agent.create_argocd_application(
            self._app_info(), "https://github.com/x/gitops.git"
        )
        self.assertFalse(result)

    def test_manifest_content(self):
        """Generated manifest must include app name and gitops URL."""
        from agent import AppInfo
        info = AppInfo(name="my-svc", description="desc")
        gitops_url = "https://github.com/org/my-svc-gitops.git"
        manifest = self.agent._generate_argocd_manifest(info, gitops_url)

        self.assertIn("name: my-svc", manifest)
        self.assertIn(f"repoURL: {gitops_url}", manifest)
        self.assertIn("argoproj.io/v1alpha1", manifest)
        self.assertIn("automated:", manifest)
        self.assertIn("selfHeal: true", manifest)
        self.assertIn("retry:", manifest)

    def test_manifest_has_retry_policy(self):
        from agent import AppInfo
        manifest = self.agent._generate_argocd_manifest(
            AppInfo(name="x", description="d"), "https://github.com/x/y.git"
        )
        self.assertIn("limit: 5", manifest)
        self.assertIn("backoff:", manifest)


# ---------------------------------------------------------------------------
# Tests: run_onboarding_flow (end-to-end with mocks)
# ---------------------------------------------------------------------------

class TestRunOnboardingFlow(unittest.TestCase):

    def setUp(self):
        self.agent = _make_agent(dry_run=False)
        from agent import AppInfo, RepositoryInfo
        self.app_info = AppInfo(name="inventory-api", description="Test")
        self.repo_info = RepositoryInfo(
            source_repo_url="https://github.com/u/inventory-api-source.git",
            gitops_repo_url="https://github.com/u/inventory-api-gitops.git",
            source_repo_id="1",
            gitops_repo_id="2",
        )

    def _patch_all(self, extract_rv=None, repo_rv=None, populate_rv=True, argocd_rv=True):
        extract_rv = extract_rv or self.app_info
        repo_rv = repo_rv or self.repo_info
        return (
            patch.object(self.agent, 'extract_app_info', return_value=extract_rv),
            patch.object(self.agent, 'create_github_repo', return_value=repo_rv),
            patch.object(self.agent, 'populate_repo_from_stack', return_value=populate_rv),
            patch.object(self.agent, 'create_argocd_application', return_value=argocd_rv),
        )

    def test_happy_path_returns_success(self):
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3]:
            result = self.agent.run_onboarding_flow("Deploy inventory-api")

        self.assertTrue(result['success'])
        self.assertIsNone(result['error'])
        self.assertTrue(result['argocd_created'])

    def test_source_populate_failure_stops_flow(self):
        patches = self._patch_all(populate_rv=False)
        with patches[0], patches[1], patches[2], patches[3]:
            result = self.agent.run_onboarding_flow("Deploy inventory-api")

        self.assertFalse(result['success'])
        self.assertIsNotNone(result['error'])

    def test_argocd_failure_records_in_result(self):
        patches = self._patch_all(argocd_rv=False)
        with patches[0], patches[1], patches[2], patches[3]:
            result = self.agent.run_onboarding_flow("Deploy inventory-api")

        # ArgoCD failure doesn't fail the overall flow ÃÂ¢ÃÂÃÂ argocd_created is False
        self.assertTrue(result['success'])
        self.assertFalse(result['argocd_created'])

    def test_result_has_expected_keys(self):
        patches = self._patch_all()
        with patches[0], patches[1], patches[2], patches[3]:
            result = self.agent.run_onboarding_flow("Deploy inventory-api")

        for key in ('success', 'app_info', 'repositories', 'argocd_created', 'error', 'timestamp', 'dry_run'):
            self.assertIn(key, result)

    def test_dry_run_flow_succeeds_without_credentials(self):
        agent = _make_agent(dry_run=True)
        with patch.object(agent, 'extract_app_info', return_value=self.app_info):
            result = agent.run_onboarding_flow("Deploy inventory-api")

        self.assertTrue(result['success'])
        self.assertTrue(result['dry_run'])

    def test_exception_in_extract_sets_error(self):
        with patch.object(self.agent, 'extract_app_info', side_effect=RuntimeError("boom")):
            result = self.agent.run_onboarding_flow("Deploy inventory-api")

        self.assertFalse(result['success'])
        self.assertIn("boom", result['error'])


# ---------------------------------------------------------------------------
# Tests: Jinja2 template rendering (_copy_template_files path)
# ---------------------------------------------------------------------------

class TestTemplateRendering(unittest.TestCase):

    def test_variables_substituted(self):
        from jinja2 import Environment
        from agent import AppInfo
        info = AppInfo(name="order-svc", description="Order service")
        tpl = "name: {{appName}}\ndesc: {{description}}\nimage: {{imageName}}"
        rendered = Environment().from_string(tpl).render(
            appName=info.name,
            description=info.description,
            imageName=f"user/{info.name}",
        )
        self.assertIn("order-svc", rendered)
        self.assertIn("Order service", rendered)
        self.assertIn("user/order-svc", rendered)

    def test_argocd_yaml_renders_correctly(self):
        from jinja2 import Environment
        tpl = "repoURL: {{gitopsUrl}}\napp: {{appName}}"
        rendered = Environment().from_string(tpl).render(
            gitopsUrl="https://github.com/u/r.git",
            appName="my-app",
        )
        self.assertIn("https://github.com/u/r.git", rendered)
        self.assertIn("my-app", rendered)


# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # Ensure a clean env for direct execution
    _set_env(
        OPENROUTER_API_KEY='test-key',
        GITHUB_TOKEN='test-token',
        GITHUB_USERNAME='test-user',
        NODEJS_TEMPLATE_PATH='/tmp',
        GITOPS_TEMPLATE_PATH='/tmp',
    )
    unittest.main(verbosity=2)
