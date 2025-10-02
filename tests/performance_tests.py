#!/usr/bin/env python3
"""
Performance Tests for Golden Path Demo
Tests system performance under various load conditions
"""

import argparse
import json
import logging
import psutil
import time
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import requests
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceTestSuite:
    """Comprehensive performance testing for Golden Path demo"""

    def __init__(self):
        self.results = []
        self.baseline_file = Path("performance_baseline.json")
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)

    def measure_resource_usage(self, duration: int = 60) -> dict:
        """Measure system resource usage over time"""
        logger.info(f"Measuring resource usage for {duration} seconds")

        cpu_samples = []
        memory_samples = []
        disk_io_samples = []
        network_io_samples = []

        start_time = time.time()

        while time.time() - start_time < duration:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_samples.append(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_samples.append({
                "percent": memory.percent,
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3)
            })

            # Disk I/O
            disk_io = psutil.disk_io_counters()
            if disk_io:
                disk_io_samples.append({
                    "read_mb": disk_io.read_bytes / (1024**2),
                    "write_mb": disk_io.write_bytes / (1024**2)
                })

            # Network I/O
            network_io = psutil.net_io_counters()
            if network_io:
                network_io_samples.append({
                    "sent_mb": network_io.bytes_sent / (1024**2),
                    "recv_mb": network_io.bytes_recv / (1024**2)
                })

        return {
            "duration": duration,
            "cpu": {
                "avg": statistics.mean(cpu_samples),
                "max": max(cpu_samples),
                "min": min(cpu_samples),
                "samples": cpu_samples
            },
            "memory": {
                "avg_percent": statistics.mean([m["percent"] for m in memory_samples]),
                "max_percent": max([m["percent"] for m in memory_samples]),
                "avg_used_gb": statistics.mean([m["used_gb"] for m in memory_samples]),
                "max_used_gb": max([m["used_gb"] for m in memory_samples])
            },
            "samples_count": len(cpu_samples)
        }

    def test_command_performance(self, command: str, iterations: int = 10) -> dict:
        """Test command execution performance"""
        logger.info(f"Testing command performance: {command} ({iterations} iterations)")

        execution_times = []
        success_count = 0
        error_messages = []

        for i in range(iterations):
            try:
                start_time = time.time()
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                end_time = time.time()

                execution_time = end_time - start_time
                execution_times.append(execution_time)

                if result.returncode == 0:
                    success_count += 1
                else:
                    error_messages.append(result.stderr.strip())

                logger.debug(f"Iteration {i+1}: {execution_time:.3f}s")

            except subprocess.TimeoutExpired:
                error_messages.append(f"Command timed out after 30 seconds")
            except Exception as e:
                error_messages.append(str(e))

        return {
            "command": command,
            "iterations": iterations,
            "success_count": success_count,
            "success_rate": success_count / iterations * 100,
            "execution_times": {
                "avg": statistics.mean(execution_times) if execution_times else 0,
                "min": min(execution_times) if execution_times else 0,
                "max": max(execution_times) if execution_times else 0,
                "median": statistics.median(execution_times) if execution_times else 0,
                "stdev": statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            },
            "errors": error_messages[:5]  # Keep first 5 errors
        }

    def test_concurrent_load(self, task_func, num_threads: int = 10, tasks_per_thread: int = 5) -> dict:
        """Test system performance under concurrent load"""
        logger.info(f"Testing concurrent load: {num_threads} threads, {tasks_per_thread} tasks each")

        total_tasks = num_threads * tasks_per_thread
        completed_tasks = []
        failed_tasks = []

        def worker_task(thread_id: int):
            for task_id in range(tasks_per_thread):
                task_start = time.time()
                try:
                    result = task_func(f"thread-{thread_id}-task-{task_id}")
                    task_end = time.time()
                    completed_tasks.append({
                        "thread_id": thread_id,
                        "task_id": task_id,
                        "duration": task_end - task_start,
                        "result": result
                    })
                except Exception as e:
                    failed_tasks.append({
                        "thread_id": thread_id,
                        "task_id": task_id,
                        "error": str(e)
                    })

        # Monitor resources during load test
        monitoring_thread = threading.Thread(
            target=lambda: self.monitor_resources_during_test(total_tasks * 2)
        )
        monitoring_thread.start()

        # Execute concurrent tasks
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()  # Wait for completion
        end_time = time.time()

        monitoring_thread.join(timeout=5)

        return {
            "total_tasks": total_tasks,
            "num_threads": num_threads,
            "completed_tasks": len(completed_tasks),
            "failed_tasks": len(failed_tasks),
            "success_rate": len(completed_tasks) / total_tasks * 100,
            "total_duration": end_time - start_time,
            "avg_task_duration": statistics.mean([t["duration"] for t in completed_tasks]) if completed_tasks else 0,
            "throughput": len(completed_tasks) / (end_time - start_time) if end_time > start_time else 0
        }

    def monitor_resources_during_test(self, duration: int):
        """Monitor resources during a test"""
        end_time = time.time() + duration
        samples = []

        while time.time() < end_time:
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            samples.append({
                "timestamp": time.time(),
                "cpu": cpu,
                "memory_percent": memory.percent
            })

        return samples

    def test_api_performance(self, url: str, method: str = "GET",
                           concurrent_requests: int = 20, total_requests: int = 100) -> dict:
        """Test API endpoint performance"""
        logger.info(f"Testing API performance: {method} {url}")

        def make_request(request_id: str):
            start_time = time.time()
            try:
                response = requests.request(method, url, timeout=10)
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "duration": end_time - start_time,
                    "response_size": len(response.content)
                }
            except Exception as e:
                return {
                    "request_id": request_id,
                    "error": str(e),
                    "duration": time.time() - start_time
                }

        # Execute concurrent requests
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            futures = [
                executor.submit(make_request, f"req-{i}")
                for i in range(total_requests)
            ]
            responses = [future.result() for future in as_completed(futures)]
        end_time = time.time()

        # Analyze results
        successful_responses = [r for r in responses if "error" not in r and r.get("status_code", 0) < 400]
        failed_responses = [r for r in responses if "error" in r or r.get("status_code", 0) >= 400]

        if successful_responses:
            durations = [r["duration"] for r in successful_responses]
            status_codes = [r["status_code"] for r in successful_responses]
        else:
            durations = []
            status_codes = []

        return {
            "url": url,
            "method": method,
            "total_requests": total_requests,
            "concurrent_requests": concurrent_requests,
            "successful_requests": len(successful_responses),
            "failed_requests": len(failed_responses),
            "success_rate": len(successful_responses) / total_requests * 100,
            "total_duration": end_time - start_time,
            "requests_per_second": len(successful_responses) / (end_time - start_time) if end_time > start_time else 0,
            "response_times": {
                "avg": statistics.mean(durations) if durations else 0,
                "min": min(durations) if durations else 0,
                "max": max(durations) if durations else 0,
                "median": statistics.median(durations) if durations else 0,
                "p95": statistics.quantiles(durations, n=20)[18] if len(durations) > 20 else 0
            },
            "status_codes": dict(zip(*[(k, status_codes.count(k)) for k in set(status_codes)])) if status_codes else {}
        }

    def test_memory_leak(self, test_func, iterations: int = 100) -> dict:
        """Test for memory leaks in a function"""
        logger.info(f"Testing for memory leaks: {iterations} iterations")

        memory_samples = []
        process = psutil.Process()

        for i in range(iterations):
            # Execute test function
            test_func(f"iteration-{i}")

            # Measure memory usage
            memory_info = process.memory_info()
            memory_samples.append({
                "iteration": i,
                "rss_mb": memory_info.rss / (1024**2),
                "vms_mb": memory_info.vms / (1024**2)
            })

            # Force garbage collection
            import gc
            gc.collect()

        # Analyze memory growth
        rss_values = [s["rss_mb"] for s in memory_samples]
        memory_growth = rss_values[-1] - rss_values[0] if len(rss_values) > 1 else 0

        return {
            "iterations": iterations,
            "initial_memory_mb": rss_values[0] if rss_values else 0,
            "final_memory_mb": rss_values[-1] if rss_values else 0,
            "memory_growth_mb": memory_growth,
            "avg_memory_mb": statistics.mean(rss_values) if rss_values else 0,
            "max_memory_mb": max(rss_values) if rss_values else 0,
            "memory_trend": "increasing" if memory_growth > 50 else "stable",
            "samples": memory_samples[::10]  # Every 10th sample
        }

    def save_baseline(self, results: dict):
        """Save performance baseline for future comparison"""
        baseline = {
            "timestamp": datetime.now().isoformat(),
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                "platform": psutil.platform.platform()
            },
            "results": results
        }

        with open(self.baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)

        logger.info(f"Performance baseline saved to {self.baseline_file}")

    def compare_with_baseline(self, current_results: dict) -> dict:
        """Compare current results with baseline"""
        if not self.baseline_file.exists():
            logger.warning("No baseline file found for comparison")
            return {"baseline_available": False}

        with open(self.baseline_file, 'r') as f:
            baseline = json.load(f)

        comparison = {
            "baseline_available": True,
            "baseline_timestamp": baseline["timestamp"],
            "comparisons": []
        }

        # Compare each metric
        for test_name, current_data in current_results.items():
            if test_name in baseline["results"]:
                baseline_data = baseline["results"][test_name]

                test_comparison = {
                    "test_name": test_name,
                    "status": "similar"
                }

                # Compare based on test type
                if "success_rate" in current_data and "success_rate" in baseline_data:
                    rate_diff = abs(current_data["success_rate"] - baseline_data["success_rate"])
                    if rate_diff > 10:
                        test_comparison["status"] = "degraded" if current_data["success_rate"] < baseline_data["success_rate"] else "improved"
                    test_comparison["success_rate_change"] = rate_diff

                if "avg" in current_data.get("execution_times", {}) and "avg" in baseline_data.get("execution_times", {}):
                    time_ratio = current_data["execution_times"]["avg"] / baseline_data["execution_times"]["avg"]
                    if time_ratio > 1.2:
                        test_comparison["status"] = "slower"
                    elif time_ratio < 0.8:
                        test_comparison["status"] = "faster"
                    test_comparison["performance_ratio"] = time_ratio

                comparison["comparisons"].append(test_comparison)

        return comparison

    def run_comprehensive_performance_tests(self) -> dict:
        """Run all performance tests"""
        logger.info("Starting comprehensive performance test suite")

        results = {}

        # Test 1: System resource baseline
        logger.info("Test 1: System resource baseline")
        results["resource_baseline"] = self.measure_resource_usage(duration=30)

        # Test 2: Command performance
        logger.info("Test 2: Command performance")
        commands_to_test = [
            "kubectl version --client",
            "docker --version",
            "git --version",
            "python3 --version"
        ]

        results["command_performance"] = {}
        for cmd in commands_to_test:
            try:
                results["command_performance"][cmd.replace(" ", "_")] = self.test_command_performance(cmd, iterations=5)
            except Exception as e:
                logger.warning(f"Failed to test command {cmd}: {e}")

        # Test 3: Concurrent load test
        logger.info("Test 3: Concurrent load test")

        def dummy_task(task_id: str) -> str:
            """Dummy task for load testing"""
            time.sleep(0.1)
            return f"completed-{task_id}"

        results["concurrent_load"] = self.test_concurrent_load(
            dummy_task, num_threads=5, tasks_per_thread=4
        )

        # Test 4: Memory leak test
        logger.info("Test 4: Memory leak test")

        def memory_test_task(iteration: str):
            """Task that allocates memory for testing"""
            data = []
            for i in range(1000):
                data.append(f"test-data-{iteration}-{i}")
            return len(data)

        results["memory_leak_test"] = self.test_memory_leak(memory_test_task, iterations=50)

        # Test 5: API performance test (if applicable)
        logger.info("Test 5: API performance test")
        # Add API endpoints to test here if available
        # results["api_performance"] = self.test_api_performance("http://localhost:8080/health")

        # Generate overall summary
        results["summary"] = {
            "test_timestamp": datetime.now().isoformat(),
            "total_tests": len([k for k in results.keys() if k != "summary"]),
            "system_info": {
                "cpu_count": psutil.cpu_count(),
                "memory_gb": psutil.virtual_memory().total / (1024**3),
                "platform": psutil.platform.platform()
            }
        }

        # Compare with baseline
        comparison = self.compare_with_baseline(results)
        results["baseline_comparison"] = comparison

        return results

    def save_results(self, results: dict, filename: str = None):
        """Save test results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_results_{timestamp}.json"

        filepath = self.results_dir / filename
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Performance results saved to {filepath}")
        return str(filepath)


def main():
    parser = argparse.ArgumentParser(description="Golden Path Performance Test Suite")
    parser.add_argument("--baseline", action="store_true", help="Save results as baseline")
    parser.add_argument("--compare", action="store_true", help="Compare with baseline")
    parser.add_argument("--output", help="Output filename")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("--benchmark-only", action="store_true", help="Run only basic benchmarks")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    suite = PerformanceTestSuite()

    try:
        if args.benchmark_only:
            # Run only basic benchmarks
            results = {
                "resource_baseline": suite.measure_resource_usage(duration=10),
                "command_performance": {
                    "basic_commands": suite.test_command_performance("echo 'test'", iterations=3)
                }
            }
        else:
            results = suite.run_comprehensive_performance_tests()

        # Save results
        results_file = suite.save_results(results, args.output)

        # Save as baseline if requested
        if args.baseline:
            suite.save_baseline(results)

        # Print summary
        print("\\n" + "="*60)
        print("PERFORMANCE TEST SUMMARY")
        print("="*60)

        for test_name, test_data in results.items():
            if test_name == "summary":
                continue

            print(f"\\n{test_name.upper().replace('_', ' ')}:")

            if "success_rate" in test_data:
                print(f"  Success Rate: {test_data['success_rate']:.1f}%")

            if "avg" in test_data.get("execution_times", {}):
                exec_times = test_data["execution_times"]
                print(f"  Avg Execution Time: {exec_times['avg']:.3f}s")
                print(f"  Max Execution Time: {exec_times['max']:.3f}s")

            if "memory_growth_mb" in test_data:
                print(f"  Memory Growth: {test_data['memory_growth_mb']:.1f} MB")
                print(f"  Memory Trend: {test_data['memory_trend']}")

        print(f"\\nResults saved to: {results_file}")

        # Return appropriate exit code
        if "baseline_comparison" in results:
            comparison = results["baseline_comparison"]
            degraded_tests = [c for c in comparison.get("comparisons", []) if c.get("status") == "degraded"]
            if degraded_tests:
                print(f"\\n⚠️  Warning: {len(degraded_tests)} tests show performance degradation")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Performance test suite failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())