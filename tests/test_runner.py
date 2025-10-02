#!/usr/bin/env python3
"""
Golden Path Demo Test Runner
Automated test execution framework with CI/CD integration

Features:
- Parallel test execution
- Test result aggregation and reporting
- CI/CD pipeline integration
- Slack/email notifications
- Historical trend tracking
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_runner.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TestRunner:
    """Advanced test runner with parallel execution and CI/CD integration"""

    def __init__(self, config_file: str = None):
        self.config = self._load_config(config_file)
        self.workspace_dir = Path("/workspaces/ai-powered-golden-path-demo")
        self.tests_dir = self.workspace_dir / "tests"
        self.results_dir = self.tests_dir / "results"
        self.results_dir.mkdir(exist_ok=True)

        # Test suites configuration
        self.test_suites = {
            "prerequisites": {
                "script": "prerequisites_check.sh",
                "timeout": 300,
                "critical": True,
                "parallel_safe": False
            },
            "unit_tests": {
                "script": "run_unit_tests.py",
                "timeout": 600,
                "critical": True,
                "parallel_safe": True
            },
            "integration_tests": {
                "script": "golden_path_tests.py",
                "timeout": 1800,
                "critical": True,
                "parallel_safe": False
            },
            "performance_tests": {
                "script": "performance_tests.py",
                "timeout": 900,
                "critical": False,
                "parallel_safe": True
            },
            "security_tests": {
                "script": "security_scan.py",
                "timeout": 600,
                "critical": False,
                "parallel_safe": True
            }
        }

    def _load_config(self, config_file: str) -> Dict:
        """Load test runner configuration"""
        default_config = {
            "execution": {
                "max_parallel_jobs": 4,
                "retry_failed_tests": True,
                "max_retries": 2,
                "continue_on_failure": False
            },
            "notifications": {
                "slack_webhook_url": os.getenv("SLACK_WEBHOOK_URL"),
                "email_enabled": False,
                "email_smtp_server": "smtp.gmail.com",
                "email_smtp_port": 587,
                "email_recipients": []
            },
            "reporting": {
                "generate_html_report": True,
                "generate_json_report": True,
                "generate_junit_report": True,
                "trend_tracking_days": 30
            },
            "thresholds": {
                "min_success_rate": 80,
                "max_test_duration": 3600,
                "max_memory_usage": "4GB"
            }
        }

        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config

    def run_test_suite(self, suite_name: str, suite_config: Dict,
                      environment: Dict = None) -> Dict:
        """Execute a single test suite"""
        logger.info(f"Starting test suite: {suite_name}")

        start_time = datetime.now()
        script_path = self.tests_dir / suite_config["script"]

        if not script_path.exists():
            return {
                "suite_name": suite_name,
                "status": "FAILED",
                "duration": 0,
                "error": f"Test script not found: {script_path}",
                "output": "",
                "start_time": start_time.isoformat(),
                "end_time": datetime.now().isoformat()
            }

        try:
            # Prepare environment
            env = os.environ.copy()
            if environment:
                env.update(environment)

            # Execute test script
            process = subprocess.run(
                [str(script_path)],
                cwd=self.tests_dir,
                env=env,
                timeout=suite_config["timeout"],
                capture_output=True,
                text=True
            )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                "suite_name": suite_name,
                "status": "PASSED" if process.returncode == 0 else "FAILED",
                "duration": duration,
                "return_code": process.returncode,
                "output": process.stdout,
                "error": process.stderr if process.returncode != 0 else None,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "critical": suite_config["critical"]
            }

        except subprocess.TimeoutExpired:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                "suite_name": suite_name,
                "status": "TIMEOUT",
                "duration": duration,
                "error": f"Test suite timed out after {suite_config['timeout']} seconds",
                "output": "",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "critical": suite_config["critical"]
            }

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return {
                "suite_name": suite_name,
                "status": "ERROR",
                "duration": duration,
                "error": str(e),
                "output": "",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "critical": suite_config["critical"]
            }

    def run_parallel_tests(self, test_suites: Dict[str, Dict],
                          environment: Dict = None) -> List[Dict]:
        """Run multiple test suites in parallel"""
        logger.info(f"Running {len(test_suites)} test suites in parallel")

        results = []
        max_workers = self.config["execution"]["max_parallel_jobs"]

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all test suites
            future_to_suite = {
                executor.submit(self.run_test_suite, name, config, environment): name
                for name, config in test_suites.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_suite):
                suite_name = future_to_suite[future]
                try:
                    result = future.result()
                    results.append(result)

                    status = result["status"]
                    if status == "PASSED":
                        logger.info(f"✅ {suite_name}: PASSED")
                    else:
                        logger.error(f"❌ {suite_name}: {status}")
                        if result.get("error"):
                            logger.error(f"   Error: {result['error']}")

                except Exception as e:
                    logger.error(f"❌ {suite_name}: Exception - {e}")
                    results.append({
                        "suite_name": suite_name,
                        "status": "ERROR",
                        "duration": 0,
                        "error": str(e),
                        "critical": test_suites[suite_name]["critical"]
                    })

        return results

    def run_sequential_tests(self, test_suites: Dict[str, Dict],
                           environment: Dict = None) -> List[Dict]:
        """Run test suites sequentially"""
        logger.info(f"Running {len(test_suites)} test suites sequentially")

        results = []

        for suite_name, suite_config in test_suites.items():
            logger.info(f"Executing: {suite_name}")
            result = self.run_test_suite(suite_name, suite_config, environment)
            results.append(result)

            # Stop on critical failure if configured
            if (result["status"] not in ["PASSED"] and
                result["critical"] and
                not self.config["execution"]["continue_on_failure"]):
                logger.error(f"Stopping execution due to critical failure in {suite_name}")
                break

        return results

    def retry_failed_tests(self, results: List[Dict],
                          test_suites: Dict[str, Dict]) -> List[Dict]:
        """Retry failed test suites"""
        if not self.config["execution"]["retry_failed_tests"]:
            return results

        max_retries = self.config["execution"]["max_retries"]
        retry_count = 0

        while retry_count < max_retries:
            failed_suites = [
                r for r in results
                if r["status"] not in ["PASSED"] and retry_count < max_retries
            ]

            if not failed_suites:
                break

            retry_count += 1
            logger.info(f"Retry attempt {retry_count} for {len(failed_suites)} failed suites")

            retry_results = []
            for failed_result in failed_suites:
                suite_name = failed_result["suite_name"]
                if suite_name in test_suites:
                    logger.info(f"Retrying: {suite_name}")
                    retry_result = self.run_test_suite(
                        suite_name,
                        test_suites[suite_name]
                    )
                    retry_result["retry_attempt"] = retry_count
                    retry_results.append(retry_result)

            # Update results with retry outcomes
            for i, original_result in enumerate(results):
                for retry_result in retry_results:
                    if (original_result["suite_name"] == retry_result["suite_name"] and
                        retry_result["status"] == "PASSED"):
                        results[i] = retry_result
                        break

        return results

    def calculate_metrics(self, results: List[Dict]) -> Dict:
        """Calculate test execution metrics"""
        total_suites = len(results)
        passed_suites = len([r for r in results if r["status"] == "PASSED"])
        failed_suites = len([r for r in results if r["status"] in ["FAILED", "ERROR", "TIMEOUT"]])
        critical_failed = len([r for r in results if r["status"] != "PASSED" and r.get("critical", False)])

        total_duration = sum(r["duration"] for r in results)
        max_duration = max(r["duration"] for r in results) if results else 0

        success_rate = (passed_suites / total_suites * 100) if total_suites > 0 else 0

        return {
            "total_suites": total_suites,
            "passed_suites": passed_suites,
            "failed_suites": failed_suites,
            "critical_failed": critical_failed,
            "success_rate": success_rate,
            "total_duration": total_duration,
            "max_duration": max_duration,
            "overall_status": "PASSED" if critical_failed == 0 and success_rate >= self.config["thresholds"]["min_success_rate"] else "FAILED"
        }

    def generate_json_report(self, results: List[Dict], metrics: Dict) -> str:
        """Generate JSON test report"""
        report = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "runner_version": "1.0.0",
                "workspace": str(self.workspace_dir),
                "configuration": self.config
            },
            "metrics": metrics,
            "results": results
        }

        report_file = self.results_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        return str(report_file)

    def generate_html_report(self, results: List[Dict], metrics: Dict) -> str:
        """Generate HTML test report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Golden Path Demo Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .metrics { display: flex; gap: 20px; margin: 20px 0; }
        .metric { background-color: #e8f4f8; padding: 15px; border-radius: 5px; text-align: center; }
        .metric.failed { background-color: #ffe8e8; }
        .test-results { margin-top: 20px; }
        .test-suite { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .test-suite.passed { border-left: 5px solid #4CAF50; }
        .test-suite.failed { border-left: 5px solid #f44336; }
        .test-suite.timeout { border-left: 5px solid #ff9800; }
        .status { font-weight: bold; padding: 5px 10px; border-radius: 3px; color: white; }
        .status.passed { background-color: #4CAF50; }
        .status.failed { background-color: #f44336; }
        .status.timeout { background-color: #ff9800; }
        .duration { color: #666; font-size: 0.9em; }
        .error { background-color: #ffe8e8; padding: 10px; margin: 10px 0; border-radius: 3px; font-family: monospace; }
        .output { background-color: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 3px; font-family: monospace; max-height: 200px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Golden Path Demo Test Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Workspace: {workspace}</p>
    </div>

    <div class="metrics">
        <div class="metric">
            <h3>{total_suites}</h3>
            <p>Total Suites</p>
        </div>
        <div class="metric">
            <h3>{passed_suites}</h3>
            <p>Passed</p>
        </div>
        <div class="metric failed">
            <h3>{failed_suites}</h3>
            <p>Failed</p>
        </div>
        <div class="metric {'failed' if success_rate < min_success_rate else ''}">
            <h3>{success_rate:.1f}%</h3>
            <p>Success Rate</p>
        </div>
        <div class="metric">
            <h3>{total_duration:.1f}s</h3>
            <p>Total Duration</p>
        </div>
    </div>

    <div class="test-results">
        <h2>Test Suite Results</h2>
        {test_results_html}
    </div>
</body>
</html>
        """

        # Generate test results HTML
        test_results_html = ""
        for result in results:
            status_class = result["status"].lower()
            critical_badge = " 🚨" if result.get("critical") and result["status"] != "PASSED" else ""

            test_results_html += f"""
        <div class="test-suite {status_class}">
            <h3>{result['suite_name']}{critical_badge}
                <span class="status {status_class}">{result['status']}</span>
                <span class="duration">{result['duration']:.1f}s</span>
            </h3>
            """

            if result.get("error"):
                test_results_html += f'<div class="error">Error: {result["error"]}</div>'

            if result.get("output") and len(result["output"]) < 2000:
                test_results_html += f'<div class="output">{result["output"]}</div>'

            test_results_html += "</div>"

        # Format the HTML
        html_content = html_template.format(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            workspace=str(self.workspace_dir),
            total_suites=metrics["total_suites"],
            passed_suites=metrics["passed_suites"],
            failed_suites=metrics["failed_suites"],
            success_rate=metrics["success_rate"],
            total_duration=metrics["total_duration"],
            min_success_rate=self.config["thresholds"]["min_success_rate"],
            test_results_html=test_results_html
        )

        report_file = self.results_dir / f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        with open(report_file, 'w') as f:
            f.write(html_content)

        return str(report_file)

    def send_slack_notification(self, metrics: Dict, report_files: Dict):
        """Send test results to Slack"""
        webhook_url = self.config["notifications"]["slack_webhook_url"]
        if not webhook_url:
            return

        color = "good" if metrics["overall_status"] == "PASSED" else "danger"

        payload = {
            "text": f"Golden Path Demo Test Results: {metrics['overall_status']}",
            "attachments": [{
                "color": color,
                "fields": [
                    {"title": "Total Suites", "value": str(metrics["total_suites"]), "short": True},
                    {"title": "Passed", "value": str(metrics["passed_suites"]), "short": True},
                    {"title": "Failed", "value": str(metrics["failed_suites"]), "short": True},
                    {"title": "Success Rate", "value": f"{metrics['success_rate']:.1f}%", "short": True},
                    {"title": "Duration", "value": f"{metrics['total_duration']:.1f}s", "short": True},
                    {"title": "Timestamp", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "short": True}
                ]
            }]
        }

        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Slack notification sent successfully")
            else:
                logger.warning(f"Failed to send Slack notification: {response.status_code}")
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")

    def execute_test_run(self, test_names: List[str] = None,
                        environment: Dict = None,
                        parallel: bool = True) -> Dict:
        """Execute complete test run"""
        logger.info("Starting Golden Path Demo Test Runner")

        start_time = datetime.now()

        # Determine which test suites to run
        if test_names:
            test_suites_to_run = {name: self.test_suites[name]
                               for name in test_names if name in self.test_suites}
        else:
            test_suites_to_run = self.test_suites

        # Separate parallel and sequential tests
        parallel_tests = {name: config for name, config in test_suites_to_run.items()
                         if config["parallel_safe"]}
        sequential_tests = {name: config for name, config in test_suites_to_run.items()
                           if not config["parallel_safe"]}

        all_results = []

        # Run parallel tests first
        if parallel_tests:
            logger.info(f"Running {len(parallel_tests)} parallel test suites")
            parallel_results = self.run_parallel_tests(parallel_tests, environment)
            all_results.extend(parallel_results)

        # Run sequential tests
        if sequential_tests:
            logger.info(f"Running {len(sequential_tests)} sequential test suites")
            sequential_results = self.run_sequential_tests(sequential_tests, environment)
            all_results.extend(sequential_results)

        # Retry failed tests if configured
        if self.config["execution"]["retry_failed_tests"]:
            logger.info("Retrying failed tests")
            all_results = self.retry_failed_tests(all_results, test_suites_to_run)

        # Calculate metrics
        metrics = self.calculate_metrics(all_results)
        end_time = datetime.now()
        metrics["execution_time"] = (end_time - start_time).total_seconds()

        # Generate reports
        report_files = {}
        if self.config["reporting"]["generate_json_report"]:
            report_files["json"] = self.generate_json_report(all_results, metrics)

        if self.config["reporting"]["generate_html_report"]:
            report_files["html"] = self.generate_html_report(all_results, metrics)

        # Send notifications
        self.send_slack_notification(metrics, report_files)

        # Log summary
        logger.info("=" * 60)
        logger.info("TEST EXECUTION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Suites: {metrics['total_suites']}")
        logger.info(f"Passed: {metrics['passed_suites']}")
        logger.info(f"Failed: {metrics['failed_suites']}")
        logger.info(f"Success Rate: {metrics['success_rate']:.1f}%")
        logger.info(f"Duration: {metrics['total_duration']:.1f}s")
        logger.info(f"Overall Status: {metrics['overall_status']}")

        if report_files:
            logger.info("Reports generated:")
            for report_type, file_path in report_files.items():
                logger.info(f"  {report_type.upper()}: {file_path}")

        return {
            "metrics": metrics,
            "results": all_results,
            "report_files": report_files,
            "execution_time": metrics["execution_time"]
        }

    def list_available_tests(self):
        """List all available test suites"""
        print("\\nAvailable Test Suites:")
        print("=" * 40)

        for name, config in self.test_suites.items():
            status = "🚨 Critical" if config["critical"] else "ℹ️  Optional"
            parallel = "🔄 Parallel" if config["parallel_safe"] else "📋 Sequential"
            timeout = f"⏱️  {config['timeout']}s"

            print(f"{name:15} - {status} | {parallel} | {timeout}")
            print(f"{'':15}   Script: {config['script']}")
            print()

    def validate_configuration(self) -> bool:
        """Validate test runner configuration"""
        logger.info("Validating test runner configuration")

        # Check required directories
        if not self.tests_dir.exists():
            logger.error(f"Tests directory not found: {self.tests_dir}")
            return False

        # Check test scripts exist
        missing_scripts = []
        for name, config in self.test_suites.items():
            script_path = self.tests_dir / config["script"]
            if not script_path.exists():
                missing_scripts.append(f"{name}: {script_path}")

        if missing_scripts:
            logger.error("Missing test scripts:")
            for missing in missing_scripts:
                logger.error(f"  - {missing}")
            return False

        # Check results directory is writable
        try:
            test_file = self.results_dir / "test_write_permission"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            logger.error(f"Results directory not writable: {e}")
            return False

        logger.info("Configuration validation passed")
        return True


def main():
    parser = argparse.ArgumentParser(description="Golden Path Demo Test Runner")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--tests", nargs="+", help="Specific test suites to run")
    parser.add_argument("--parallel", action="store_true", default=True, help="Run tests in parallel")
    parser.add_argument("--sequential", action="store_true", help="Run tests sequentially")
    parser.add_argument("--list", action="store_true", help="List available test suites")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--env", help="Environment variables file (JSON format)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = TestRunner(args.config)

    if args.list:
        runner.list_available_tests()
        return 0

    if args.validate:
        return 0 if runner.validate_configuration() else 1

    # Load environment variables if provided
    environment = {}
    if args.env and Path(args.env).exists():
        with open(args.env, 'r') as f:
            environment = json.load(f)

    # Validate configuration before running tests
    if not runner.validate_configuration():
        logger.error("Configuration validation failed")
        return 1

    # Execute test run
    parallel = args.parallel and not args.sequential
    execution_result = runner.execute_test_run(
        test_names=args.tests,
        environment=environment,
        parallel=parallel
    )

    # Return appropriate exit code
    return 0 if execution_result["metrics"]["overall_status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())