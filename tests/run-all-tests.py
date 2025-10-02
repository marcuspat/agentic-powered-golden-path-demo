#!/usr/bin/env python3
"""
Golden Path Demo - Comprehensive Test Runner
Executes all test suites with detailed reporting and metrics
"""

import os
import sys
import json
import subprocess
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class TestRunner:
    """Comprehensive test runner for Golden Path Demo"""

    def __init__(self, quick_mode: bool = False):
        self.quick_mode = quick_mode
        self.test_results = []
        self.start_time = datetime.now()
        self.project_root = Path(__file__).parent.parent
        self.tests_dir = Path(__file__).parent

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites and return comprehensive results"""
        print("=" * 80)
        print("Golden Path Demo - Comprehensive Test Suite")
        print("=" * 80)
        print(f"Timestamp: {self.start_time.isoformat()}")
        print(f"Quick Mode: {self.quick_mode}")
        print(f"Project Root: {self.project_root}")
        print()

        # Define test suites
        test_suites = [
            {
                "name": "Phase 1: Prerequisites",
                "script": "test-phase1-prerequisites.sh",
                "type": "infrastructure",
                "critical": True,
                "description": "Validate system prerequisites and environment setup"
            },
            {
                "name": "Phase 1: idpbuilder",
                "script": "test-phase1-idpbuilder.sh",
                "type": "infrastructure",
                "critical": True,
                "description": "Validate idpbuilder installation and cluster setup"
            },
            {
                "name": "Phase 2: Stack Creation",
                "script": "test-phase2-stack-creation.sh",
                "type": "unit",
                "critical": True,
                "description": "Validate Golden Path stack template creation"
            },
            {
                "name": "Phase 3: Agent Environment",
                "script": "test-phase3-agent-env.sh",
                "type": "unit",
                "critical": True,
                "description": "Validate AI agent environment setup"
            },
            {
                "name": "Phase 3: Agent Functionality",
                "script": "test-phase3-agent-functionality.py",
                "type": "unit",
                "critical": True,
                "description": "Validate AI agent functionality"
            },
            {
                "name": "Integration Tests",
                "script": "test-integration-e2e.py",
                "type": "integration",
                "critical": True,
                "description": "End-to-end workflow integration tests"
            },
            {
                "name": "Demonstration Validation",
                "script": "validate-demonstration.sh",
                "type": "validation",
                "critical": True,
                "description": "Comprehensive demonstration readiness validation"
            },
            {
                "name": "Failure Mode Tests",
                "script": "test-failure-modes.sh",
                "type": "resilience",
                "critical": False,
                "description": "Test error handling and recovery scenarios"
            }
        ]

        # Filter tests for quick mode
        if self.quick_mode:
            test_suites = [suite for suite in test_suites if suite.get("critical", True)]

        # Run each test suite
        for suite in test_suites:
            self.run_test_suite(suite)

        # Generate final report
        return self.generate_final_report()

    def run_test_suite(self, suite: Dict[str, Any]) -> None:
        """Run a single test suite"""
        print(f"Running: {suite['name']}")
        print(f"Description: {suite['description']}")
        print(f"Type: {suite['type']}")
        print("-" * 60)

        script_path = self.tests_dir / suite['script']

        if not script_path.exists():
            self.record_test_result(suite, "skipped", 0, 0, 0, "Script not found")
            return

        start_time = time.time()
        try:
            # Make script executable
            os.chmod(script_path, 0o755)

            # Run test script
            result = subprocess.run(
                [str(script_path)],
                cwd=self.tests_dir,
                capture_output=True,
                text=True,
                timeout=300 if not self.quick_mode else 60
            )

            duration = time.time() - start_time

            # Parse results from script output
            if result.returncode == 0:
                self.record_test_result(suite, "passed", duration, result.returncode)
                print(f"✅ {suite['name']} - PASSED ({duration:.1f}s)")
            else:
                self.record_test_result(suite, "failed", duration, result.returncode, result.stderr)
                print(f"❌ {suite['name']} - FAILED ({duration:.1f}s)")
                if result.stderr:
                    print(f"   Error: {result.stderr.strip()[:200]}")

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.record_test_result(suite, "timeout", duration, -1, "Test timed out")
            print(f"⏰ {suite['name']} - TIMEOUT ({duration:.1f}s)")

        except Exception as e:
            duration = time.time() - start_time
            self.record_test_result(suite, "error", duration, -1, str(e))
            print(f"💥 {suite['name']} - ERROR ({duration:.1f}s): {e}")

        print()

    def record_test_result(self, suite: Dict[str, Any], status: str, duration: float,
                          exit_code: int, error_message: Optional[str] = None) -> None:
        """Record test result"""
        result = {
            "name": suite["name"],
            "script": suite["script"],
            "type": suite["type"],
            "critical": suite.get("critical", False),
            "description": suite["description"],
            "status": status,
            "duration": duration,
            "exit_code": exit_code,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        }

        self.test_results.append(result)

    def generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive final report"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()

        # Calculate metrics
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "passed"])
        failed_tests = len([r for r in self.test_results if r["status"] == "failed"])
        skipped_tests = len([r for r in self.test_results if r["status"] == "skipped"])
        timeout_tests = len([r for r in self.test_results if r["status"] == "timeout"])
        error_tests = len([r for r in self.test_results if r["status"] == "error"])

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        # Categorize results
        critical_tests = [r for r in self.test_results if r.get("critical", False)]
        critical_passed = len([r for r in critical_tests if r["status"] == "passed"])
        critical_success_rate = (critical_passed / len(critical_tests) * 100) if critical_tests else 0

        # Generate report
        report = {
            "test_run": {
                "timestamp": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": total_duration,
                "quick_mode": self.quick_mode,
                "project_root": str(self.project_root)
            },
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "skipped_tests": skipped_tests,
                "timeout_tests": timeout_tests,
                "error_tests": error_tests,
                "success_rate": success_rate,
                "critical_success_rate": critical_success_rate
            },
            "test_results": self.test_results,
            "categories": {
                "infrastructure": self.get_category_results("infrastructure"),
                "unit": self.get_category_results("unit"),
                "integration": self.get_category_results("integration"),
                "validation": self.get_category_results("validation"),
                "resilience": self.get_category_results("resilience")
            },
            "recommendations": self.generate_recommendations(success_rate, critical_success_rate),
            "go_no_go": self.determine_go_no_go(success_rate, critical_success_rate)
        }

        # Print summary
        self.print_summary(report)

        # Save report
        self.save_report(report)

        return report

    def get_category_results(self, category: str) -> Dict[str, Any]:
        """Get results for a specific test category"""
        category_tests = [r for r in self.test_results if r["type"] == category]
        passed = len([r for r in category_tests if r["status"] == "passed"])
        total = len(category_tests)
        success_rate = (passed / total * 100) if total > 0 else 0

        return {
            "total": total,
            "passed": passed,
            "success_rate": success_rate,
            "tests": category_tests
        }

    def generate_recommendations(self, success_rate: float, critical_success_rate: float) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []

        if critical_success_rate < 100:
            recommendations.append("Critical tests failed - address these issues before proceeding")

        if success_rate < 95:
            recommendations.append("Overall success rate below 95% - review failed tests")

        if success_rate < 80:
            recommendations.append("Significant issues detected - comprehensive review needed")

        failed_critical = [r for r in self.test_results
                          if r["status"] in ["failed", "error", "timeout"] and r.get("critical")]
        if failed_critical:
            recommendations.append(f"Address {len(failed_critical)} critical test failures")

        # Category-specific recommendations
        for category in ["infrastructure", "unit", "integration", "validation"]:
            cat_results = self.get_category_results(category)
            if cat_results["success_rate"] < 90:
                recommendations.append(f"Improve {category} test coverage and reliability")

        if success_rate >= 95 and critical_success_rate >= 95:
            recommendations.append("System is ready for demonstration")
            recommendations.append("All critical validations passed successfully")

        return recommendations

    def determine_go_no_go(self, success_rate: float, critical_success_rate: float) -> str:
        """Determine go/no-go recommendation"""
        if critical_success_rate == 100 and success_rate >= 95:
            return "GO"
        elif critical_success_rate >= 90 and success_rate >= 90:
            return "CAUTION"
        else:
            return "NO-GO"

    def print_summary(self, report: Dict[str, Any]) -> None:
        """Print test summary"""
        print("=" * 80)
        print("TEST EXECUTION SUMMARY")
        print("=" * 80)

        summary = report["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']} ({summary['success_rate']:.1f}%)")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Skipped: {summary['skipped_tests']}")
        print(f"Timeout: {summary['timeout_tests']}")
        print(f"Errors: {summary['error_tests']}")
        print(f"Critical Success Rate: {summary['critical_success_rate']:.1f}%")
        print(f"Duration: {report['test_run']['duration_seconds']:.1f} seconds")

        # Category breakdown
        print("\nCategory Breakdown:")
        for category, results in report["categories"].items():
            if results["total"] > 0:
                print(f"  {category.capitalize()}: {results['passed']}/{results['total']} "
                      f"({results['success_rate']:.1f}%)")

        # Recommendations
        print("\nRecommendations:")
        for rec in report["recommendations"]:
            print(f"  • {rec}")

        # Go/No-Go
        go_no_go = report["go_no_go"]
        if go_no_go == "GO":
            print(f"\n🟢 GO - System ready for demonstration")
        elif go_no_go == "CAUTION":
            print(f"\n🟡 CAUTION - System ready with minor issues")
        else:
            print(f"\n🔴 NO-GO - System not ready for demonstration")

    def save_report(self, report: Dict[str, Any]) -> None:
        """Save test report to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"/tmp/golden-path-test-report-{timestamp}.json"

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nDetailed report saved to: {report_file}")

        # Also save latest report
        latest_report = "/tmp/golden-path-test-report-latest.json"
        with open(latest_report, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"Latest report saved to: {latest_report}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Golden Path Demo Test Runner")
    parser.add_argument("--quick", action="store_true",
                       help="Run only critical tests (quick mode)")
    parser.add_argument("--list", action="store_true",
                       help="List available test suites")
    parser.add_argument("--category", type=str,
                       help="Run only tests from specific category")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Test timeout in seconds")

    args = parser.parse_args()

    if args.list:
        print("Available Test Suites:")
        suites = [
            ("Phase 1: Prerequisites", "test-phase1-prerequisites.sh", "infrastructure"),
            ("Phase 2: Stack Creation", "test-phase2-stack-creation.sh", "unit"),
            ("Phase 3: Agent Functionality", "test-phase3-agent-functionality.py", "unit"),
            ("Integration Tests", "test-integration-e2e.py", "integration"),
            ("Demonstration Validation", "validate-demonstration.sh", "validation"),
            ("Failure Mode Tests", "test-failure-modes.sh", "resilience")
        ]
        for name, script, category in suites:
            print(f"  {name}: {script} ({category})")
        return

    # Create and run test runner
    runner = TestRunner(quick_mode=args.quick)

    try:
        report = runner.run_all_tests()

        # Exit with appropriate code
        if report["go_no_go"] == "GO":
            sys.exit(0)
        elif report["go_no_go"] == "CAUTION":
            sys.exit(1)
        else:
            sys.exit(2)

    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Test execution failed: {e}")
        sys.exit(3)

if __name__ == "__main__":
    main()