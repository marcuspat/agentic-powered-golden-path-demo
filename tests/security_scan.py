#!/usr/bin/env python3
"""
Security Scan for Golden Path Demo
Performs comprehensive security analysis of the codebase and infrastructure
"""

import argparse
import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
import requests
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecurityScanner:
    """Comprehensive security scanning for Golden Path demo"""

    def __init__(self, workspace_dir: str = "/workspaces/ai-powered-golden-path-demo"):
        self.workspace_dir = Path(workspace_dir)
        self.results = {}
        self.scan_timestamp = datetime.now()

    def scan_for_secrets(self) -> dict:
        """Scan codebase for potential secrets and sensitive data"""
        logger.info("Scanning for secrets and sensitive data")

        # Common secret patterns
        secret_patterns = {
            "aws_access_key": r'AKIA[0-9A-Z]{16}',
            "aws_secret_key": r'[0-9a-zA-Z/+=]{40}',
            "github_token": r'ghp_[a-zA-Z0-9]{36}',
            "github_pat": r'github_pat_[a-zA-Z0-9_]{82}',
            "api_key": r'(?i)api[_-]?key["\\\'\\s]*[:=]["\\\'\\s]*[a-zA-Z0-9_-]{20,}',
            "password": r'(?i)password["\\\'\\s]*[:=]["\\\'\\s]*[^\\\'\\s"]{6,}',
            "private_key": r'-----BEGIN (RSA |OPENSSH |DSA |EC |PGP )?PRIVATE KEY-----',
            "jwt_token": r'eyJ[a-zA-Z0-9_-]*\\.eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*',
            "database_url": r'(?i)(mysql|postgresql|mongodb)://[^\\s]+',
            "slack_webhook": r'https://hooks\.slack\.com/services/[A-Z0-9]{9}/[A-Z0-9]{9}/[a-zA-Z0-9]{24}',
            "openai_key": r'sk-[a-zA-Z0-9]{48}',
        }

        findings = []
        file_extensions = ['.py', '.js', '.ts', '.json', '.yaml', '.yml', '.env', '.sh', '.md']

        for file_path in self.workspace_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix in file_extensions:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    lines = content.split('\\n')

                    for line_num, line in enumerate(lines, 1):
                        for secret_type, pattern in secret_patterns.items():
                            matches = re.finditer(pattern, line)
                            for match in matches:
                                # Skip common false positives
                                if self._is_false_positive(match.group(), line):
                                    continue

                                findings.append({
                                    "file": str(file_path.relative_to(self.workspace_dir)),
                                    "line": line_num,
                                    "type": secret_type,
                                    "match": match.group()[:50] + "..." if len(match.group()) > 50 else match.group(),
                                    "context": line.strip()[:100],
                                    "severity": self._get_severity(secret_type)
                                })

                except Exception as e:
                    logger.warning(f"Failed to scan file {file_path}: {e}")

        return {
            "scan_type": "secrets",
            "findings_count": len(findings),
            "findings": findings,
            "severity_breakdown": self._calculate_severity_breakdown(findings)
        }

    def _is_false_positive(self, match: str, line: str) -> bool:
        """Check if a match is likely a false positive"""
        false_positive_indicators = [
            "example", "sample", "test", "demo", "placeholder", "xxxxx",
            "your_", "replace_", "enter_", "...", "___", "---", "???"
        ]

        match_lower = match.lower()
        line_lower = line.lower()

        return any(indicator in line_lower for indicator in false_positive_indicators)

    def _get_severity(self, secret_type: str) -> str:
        """Get severity level for secret type"""
        high_severity = ["private_key", "aws_secret_key", "github_token", "openai_key"]
        medium_severity = ["aws_access_key", "api_key", "database_url", "password"]

        if secret_type in high_severity:
            return "HIGH"
        elif secret_type in medium_severity:
            return "MEDIUM"
        else:
            return "LOW"

    def _calculate_severity_breakdown(self, findings: list) -> dict:
        """Calculate breakdown of findings by severity"""
        breakdown = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for finding in findings:
            severity = finding.get("severity", "LOW")
            breakdown[severity] = breakdown.get(severity, 0) + 1
        return breakdown

    def scan_dependencies(self) -> dict:
        """Scan for vulnerable dependencies"""
        logger.info("Scanning for vulnerable dependencies")

        findings = []

        # Scan Python dependencies
        requirements_files = list(self.workspace_dir.rglob('requirements*.txt'))
        for req_file in requirements_files:
            try:
                content = req_file.read_text()
                dependencies = content.strip().split('\\n')

                for dep in dependencies:
                    if dep.strip() and not dep.startswith('#'):
                        findings.append({
                            "file": str(req_file.relative_to(self.workspace_dir)),
                            "dependency": dep.strip(),
                            "ecosystem": "python",
                            "vulnerability_check": "pending"  # Would need external scanner for actual check
                        })
            except Exception as e:
                logger.warning(f"Failed to scan {req_file}: {e}")

        # Scan package.json files
        package_files = list(self.workspace_dir.rglob('package.json'))
        for pkg_file in package_files:
            try:
                content = json.loads(pkg_file.read_text())
                deps = content.get('dependencies', {})
                dev_deps = content.get('devDependencies', {})

                all_deps = {**deps, **dev_deps}
                for name, version in all_deps.items():
                    findings.append({
                        "file": str(pkg_file.relative_to(self.workspace_dir)),
                        "dependency": f"{name}@{version}",
                        "ecosystem": "nodejs",
                        "vulnerability_check": "pending"
                    })
            except Exception as e:
                logger.warning(f"Failed to scan {pkg_file}: {e}")

        return {
            "scan_type": "dependencies",
            "dependencies_count": len(findings),
            "findings": findings
        }

    def scan_file_permissions(self) -> dict:
        """Scan for insecure file permissions"""
        logger.info("Scanning file permissions")

        sensitive_files = []
        for file_path in self.workspace_dir.rglob('*'):
            if file_path.is_file():
                stat_info = file_path.stat()
                mode = oct(stat_info.st_mode)[-3:]

                # Check for world-writable files
                if mode[-1] in ['2', '3', '6', '7']:  # World writable
                    sensitive_files.append({
                        "file": str(file_path.relative_to(self.workspace_dir)),
                        "permissions": mode,
                        "issue": "world_writable",
                        "severity": "MEDIUM"
                    })

                # Check for executable scripts with sensitive names
                if (file_path.name.lower().endswith(('.sh', '.py', '.js')) and
                    mode[0] in ['4', '5', '6', '7'] and  # Owner executable
                    any(keyword in file_path.name.lower() for keyword in ['key', 'secret', 'token', 'pass'])):
                    sensitive_files.append({
                        "file": str(file_path.relative_to(self.workspace_dir)),
                        "permissions": mode,
                        "issue": "sensitive_executable",
                        "severity": "HIGH"
                    })

        return {
            "scan_type": "file_permissions",
            "issues_count": len(sensitive_files),
            "findings": sensitive_files
        }

    def scan_insecure_configurations(self) -> dict:
        """Scan for insecure configurations"""
        logger.info("Scanning for insecure configurations")

        findings = []

        # Scan Kubernetes manifests
        yaml_files = list(self.workspace_dir.rglob('*.yaml')) + list(self.workspace_dir.rglob('*.yml'))

        for yaml_file in yaml_files:
            try:
                content = yaml_file.read_text()

                # Check for insecure configurations
                if 'runAsUser: 0' in content or 'privileged: true' in content:
                    findings.append({
                        "file": str(yaml_file.relative_to(self.workspace_dir)),
                        "issue": "privileged_container",
                        "severity": "HIGH",
                        "description": "Container running with elevated privileges"
                    })

                if 'hostNetwork: true' in content or 'hostPID: true' in content:
                    findings.append({
                        "file": str(yaml_file.relative_to(self.workspace_dir)),
                        "issue": "host_access",
                        "severity": "HIGH",
                        "description": "Container has access to host resources"
                    })

                if 'imagePullPolicy: Never' in content and 'image: localhost' not in content:
                    findings.append({
                        "file": str(yaml_file.relative_to(self.workspace_dir)),
                        "issue": "no_image_pull_policy",
                        "severity": "MEDIUM",
                        "description": "Container image may not be updated"
                    })

            except Exception as e:
                logger.warning(f"Failed to scan {yaml_file}: {e}")

        # Check for hardcoded URLs in configurations
        config_files = list(self.workspace_dir.rglob('*.config')) + list(self.workspace_dir.rglob('*.conf'))
        for config_file in config_files:
            try:
                content = config_file.read_text()
                if 'http://' in content and 'localhost' not in content:
                    findings.append({
                        "file": str(config_file.relative_to(self.workspace_dir)),
                        "issue": "insecure_url",
                        "severity": "LOW",
                        "description": "HTTP URL detected (should use HTTPS)"
                    })
            except Exception as e:
                logger.warning(f"Failed to scan {config_file}: {e}")

        return {
            "scan_type": "insecure_configurations",
            "findings_count": len(findings),
            "findings": findings
        }

    def scan_code_quality(self) -> dict:
        """Scan for code quality issues that could impact security"""
        logger.info("Scanning for code quality issues")

        findings = []

        # Scan Python files
        py_files = list(self.workspace_dir.rglob('*.py'))

        for py_file in py_files:
            try:
                content = py_file.read_text()
                lines = content.split('\\n')

                for line_num, line in enumerate(lines, 1):
                    line = line.strip()

                    # Check for eval/exec usage
                    if line.startswith('eval(') or line.startswith('exec('):
                        findings.append({
                            "file": str(py_file.relative_to(self.workspace_dir)),
                            "line": line_num,
                            "issue": "dynamic_code_execution",
                            "severity": "HIGH",
                            "code": line[:80]
                        })

                    # Check for shell command execution
                    if any(func in line for func in ['os.system(', 'subprocess.call(', 'subprocess.run(']):
                        if 'shell=True' in line:
                            findings.append({
                                "file": str(py_file.relative_to(self.workspace_dir)),
                                "line": line_num,
                                "issue": "shell_injection_risk",
                                "severity": "MEDIUM",
                                "code": line[:80]
                            })

                    # Check for hardcoded credentials in code
                    if '=' in line and any(keyword in line.lower() for keyword in ['password', 'secret', 'token', 'key']):
                        if '"' in line or "'" in line:
                            findings.append({
                                "file": str(py_file.relative_to(self.workspace_dir)),
                                "line": line_num,
                                "issue": "hardcoded_credential",
                                "severity": "MEDIUM",
                                "code": line[:80]
                            })

            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")

        return {
            "scan_type": "code_quality",
            "findings_count": len(findings),
            "findings": findings
        }

    def calculate_security_score(self, scan_results: dict) -> dict:
        """Calculate overall security score"""
        total_findings = 0
        high_severity = 0
        medium_severity = 0
        low_severity = 0

        for scan_type, results in scan_results.items():
            if isinstance(results, dict) and "findings" in results:
                total_findings += len(results["findings"])

                if "severity_breakdown" in results:
                    breakdown = results["severity_breakdown"]
                    high_severity += breakdown.get("HIGH", 0)
                    medium_severity += breakdown.get("MEDIUM", 0)
                    low_severity += breakdown.get("LOW", 0)
                else:
                    # Count severity from individual findings
                    for finding in results["findings"]:
                        severity = finding.get("severity", "LOW")
                        if severity == "HIGH":
                            high_severity += 1
                        elif severity == "MEDIUM":
                            medium_severity += 1
                        else:
                            low_severity += 1

        # Calculate security score (0-100)
        # High severity: -20 points, Medium: -10 points, Low: -5 points
        base_score = 100
        score = max(0, base_score - (high_severity * 20) - (medium_severity * 10) - (low_severity * 5))

        return {
            "security_score": score,
            "total_findings": total_findings,
            "severity_breakdown": {
                "HIGH": high_severity,
                "MEDIUM": medium_severity,
                "LOW": low_severity
            },
            "risk_level": "LOW" if score >= 80 else "MEDIUM" if score >= 60 else "HIGH",
            "recommendations": self._generate_recommendations(high_severity, medium_severity, low_severity)
        }

    def _generate_recommendations(self, high: int, medium: int, low: int) -> list:
        """Generate security recommendations based on findings"""
        recommendations = []

        if high > 0:
            recommendations.append("URGENT: Address all HIGH severity findings immediately")
            recommendations.append("Review and remove any exposed secrets or private keys")
            recommendations.append("Eliminate privileged container configurations")

        if medium > 0:
            recommendations.append("Review MEDIUM severity findings for security improvements")
            recommendations.append("Implement proper secret management (environment variables, vaults)")
            recommendations.append("Review file permissions and access controls")

        if low > 0:
            recommendations.append("Consider addressing LOW severity findings for hardening")
            recommendations.append("Implement HTTPS everywhere possible")
            recommendations.append("Add input validation and sanitization")

        if high == 0 and medium == 0 and low == 0:
            recommendations.append("Excellent security posture! Continue regular security scans")

        return recommendations

    def run_comprehensive_scan(self) -> dict:
        """Run all security scans"""
        logger.info("Starting comprehensive security scan")

        scan_results = {
            "scan_metadata": {
                "timestamp": self.scan_timestamp.isoformat(),
                "workspace": str(self.workspace_dir),
                "scanner_version": "1.0.0"
            }
        }

        # Run all scan types
        scan_types = [
            ("secrets", self.scan_for_secrets),
            ("dependencies", self.scan_dependencies),
            ("file_permissions", self.scan_file_permissions),
            ("insecure_configurations", self.scan_insecure_configurations),
            ("code_quality", self.scan_code_quality)
        ]

        for scan_name, scan_func in scan_types:
            try:
                logger.info(f"Running {scan_name} scan...")
                scan_results[scan_name] = scan_func()
            except Exception as e:
                logger.error(f"Failed to run {scan_name} scan: {e}")
                scan_results[scan_name] = {
                    "scan_type": scan_name,
                    "error": str(e),
                    "findings_count": 0,
                    "findings": []
                }

        # Calculate overall security score
        scan_results["security_score"] = self.calculate_security_score(scan_results)

        return scan_results

    def generate_report(self, results: dict, output_format: str = "json") -> str:
        """Generate security scan report"""
        if output_format == "json":
            return json.dumps(results, indent=2)

        elif output_format == "html":
            html_content = self._generate_html_report(results)
            return html_content

        else:
            return json.dumps(results, indent=2)

    def _generate_html_report(self, results: dict) -> str:
        """Generate HTML security report"""
        score_data = results.get("security_score", {})

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Golden Path Security Scan Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .score {{ font-size: 48px; font-weight: bold; text-align: center; margin: 20px 0; }}
        .score.high {{ color: #d32f2f; }}
        .score.medium {{ color: #f57c00; }}
        .score.low {{ color: #388e3c; }}
        .scan-section {{ margin: 20px 0; border: 1px solid #ddd; border-radius: 5px; }}
        .scan-header {{ background-color: #e9ecef; padding: 15px; font-weight: bold; }}
        .scan-content {{ padding: 15px; }}
        .finding {{ border-left: 4px solid #ddd; margin: 10px 0; padding: 10px; }}
        .finding.high {{ border-left-color: #d32f2f; }}
        .finding.medium {{ border-left-color: #f57c00; }}
        .finding.low {{ border-left-color: #388e3c; }}
        .severity {{ padding: 2px 8px; border-radius: 3px; color: white; font-size: 12px; }}
        .severity.high {{ background-color: #d32f2f; }}
        .severity.medium {{ background-color: #f57c00; }}
        .severity.low {{ background-color: #388e3c; }}
        .file-path {{ font-family: monospace; background-color: #f8f9fa; padding: 2px 4px; }}
        .recommendations {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Golden Path Security Scan Report</h1>
        <p>Generated: {results.get('scan_metadata', {}).get('timestamp', 'Unknown')}</p>
        <p>Workspace: {results.get('scan_metadata', {}).get('workspace', 'Unknown')}</p>
    </div>

    <div class="score {score_data.get('risk_level', 'unknown').lower()}">
        Security Score: {score_data.get('security_score', 0)}/100
        <div style="font-size: 16px; font-weight: normal;">
            Risk Level: {score_data.get('risk_level', 'UNKNOWN').upper()}
        </div>
    </div>

    <div class="summary">
        <h2>Summary</h2>
        <p>Total Findings: {score_data.get('total_findings', 0)}</p>
        <p>High Severity: {score_data.get('severity_breakdown', {}).get('HIGH', 0)}</p>
        <p>Medium Severity: {score_data.get('severity_breakdown', {}).get('MEDIUM', 0)}</p>
        <p>Low Severity: {score_data.get('severity_breakdown', {}).get('LOW', 0)}</p>
    </div>
"""

        # Add recommendations
        recommendations = score_data.get('recommendations', [])
        if recommendations:
            html += '<div class="recommendations"><h2>Recommendations</h2><ul>'
            for rec in recommendations:
                html += f'<li>{rec}</li>'
            html += '</ul></div>'

        # Add detailed findings
        for scan_name, scan_data in results.items():
            if scan_name in ['scan_metadata', 'security_score']:
                continue

            if isinstance(scan_data, dict) and 'findings' in scan_data:
                findings = scan_data['findings']
                if findings:
                    html += f'''
    <div class="scan-section">
        <div class="scan-header">{scan_name.replace('_', ' ').title()} ({len(findings)} findings)</div>
        <div class="scan-content">
'''
                    for finding in findings[:10]:  # Limit to first 10 findings
                        severity = finding.get('severity', 'LOW').lower()
                        file_path = finding.get('file', 'Unknown')
                        line = finding.get('line', '')
                        description = finding.get('description', finding.get('issue', ''))

                        html += f'''
            <div class="finding {severity}">
                <span class="severity {severity}">{finding.get('severity', 'LOW')}</span>
                <span class="file-path">{file_path}:{line}</span>
                <p>{description}</p>
            </div>
'''

                    if len(findings) > 10:
                        html += f'<p><em>... and {len(findings) - 10} more findings</em></p>'

                    html += '''
        </div>
    </div>
'''

        html += '''
</body>
</html>
'''
        return html

    def save_report(self, results: dict, filename: str = None, format: str = "json") -> str:
        """Save security scan report to file"""
        if not filename:
            timestamp = self.scan_timestamp.strftime("%Y%m%d_%H%M%S")
            extension = "html" if format == "html" else "json"
            filename = f"security_report_{timestamp}.{extension}"

        report_path = self.workspace_dir / "tests" / "results" / filename
        report_path.parent.mkdir(exist_ok=True)

        report_content = self.generate_report(results, format)
        report_path.write_text(report_content)

        logger.info(f"Security report saved to {report_path}")
        return str(report_path)


def main():
    parser = argparse.ArgumentParser(description="Golden Path Security Scanner")
    parser.add_argument("--output", help="Output filename")
    parser.add_argument("--format", choices=["json", "html"], default="json", help="Output format")
    parser.add_argument("--scan-type", choices=["secrets", "dependencies", "permissions", "config", "quality"], help="Specific scan to run")
    parser.add_argument("--workspace", default="/workspaces/ai-powered-golden-path-demo", help="Workspace directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scanner = SecurityScanner(args.workspace)

    try:
        if args.scan_type:
            # Run specific scan
            scan_methods = {
                "secrets": scanner.scan_for_secrets,
                "dependencies": scanner.scan_dependencies,
                "permissions": scanner.scan_file_permissions,
                "config": scanner.scan_insecure_configurations,
                "quality": scanner.scan_code_quality
            }

            if args.scan_type in scan_methods:
                results = {
                    "scan_metadata": {
                        "timestamp": scanner.scan_timestamp.isoformat(),
                        "workspace": str(scanner.workspace_dir),
                        "scanner_version": "1.0.0"
                    },
                    args.scan_type: scan_methods[args.scan_type]()
                }
                results["security_score"] = scanner.calculate_security_score(results)
            else:
                logger.error(f"Unknown scan type: {args.scan_type}")
                return 1
        else:
            # Run comprehensive scan
            results = scanner.run_comprehensive_scan()

        # Save report
        report_file = scanner.save_report(results, args.output, args.format)

        # Print summary
        score_data = results.get("security_score", {})
        print("\\n" + "="*60)
        print("SECURITY SCAN SUMMARY")
        print("="*60)
        print(f"Security Score: {score_data.get('security_score', 0)}/100")
        print(f"Risk Level: {score_data.get('risk_level', 'UNKNOWN')}")
        print(f"Total Findings: {score_data.get('total_findings', 0)}")

        breakdown = score_data.get('severity_breakdown', {})
        print(f"High Severity: {breakdown.get('HIGH', 0)}")
        print(f"Medium Severity: {breakdown.get('MEDIUM', 0)}")
        print(f"Low Severity: {breakdown.get('LOW', 0)}")

        print(f"\\nReport saved to: {report_file}")

        # Return exit code based on severity
        if score_data.get('severity_breakdown', {}).get('HIGH', 0) > 0:
            return 1  # Fail on high severity findings
        else:
            return 0

    except Exception as e:
        logger.error(f"Security scan failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())