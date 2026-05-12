"""Micro-benchmark for the credential-scanning walker.

The scanner is intended to run on every pre-commit and on every CI build,
so it must be cheap. Targets:

- Per-file: scan one ~1 KiB file in < 1 ms.
- Whole-repo: scan ``cnoe-stacks/`` + ``agent/`` in well under a second on
  a developer laptop.

Uses ``pytest-benchmark`` if available; else falls back to ``timeit``.
"""

from __future__ import annotations

import timeit
from pathlib import Path
from statistics import mean

import pytest

scanner = pytest.importorskip(
    "tests.security._scanner",
    reason="scanner helpers not yet landed",
)

pytestmark = pytest.mark.performance


_SAMPLE_FILE_CONTENT = b"""\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inventory-api
  namespace: inventory-api
  labels:
    app.kubernetes.io/name: inventory-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: inventory-api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: inventory-api
    spec:
      containers:
        - name: inventory-api
          image: ghcr.io/cnoe-io/nodejs-hello:latest
          ports:
            - containerPort: 8080
          env:
            - name: OTEL_SERVICE_NAME
              value: inventory-api
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: http://otel-collector.observability.svc.cluster.local:4318
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8080
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
""" * 8  # ~6 KiB per file


def _seed(root: Path, n_files: int) -> None:
    for i in range(n_files):
        sub = root / f"app-{i:03d}"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / "deployment.yaml").write_bytes(_SAMPLE_FILE_CONTENT)


def test_scan_single_file_under_budget(tmp_path: Path, benchmark=None) -> None:
    (tmp_path / "x.yaml").write_bytes(_SAMPLE_FILE_CONTENT)

    def _scan_once() -> None:
        scanner.scan([tmp_path], repo_root=tmp_path)

    if benchmark is not None:
        benchmark(_scan_once)
        return

    runs = 200
    avg = mean(timeit.repeat(_scan_once, number=1, repeat=runs))
    assert avg < 0.005, f"single-file scan too slow: avg={avg:.6f}s (budget 5ms)"


def test_scan_100_files_under_budget(tmp_path: Path) -> None:
    _seed(tmp_path, 100)
    start = timeit.default_timer()
    findings = scanner.scan([tmp_path], repo_root=tmp_path)
    elapsed = timeit.default_timer() - start
    # No matches expected — the fixture content has no secrets.
    assert findings == []
    assert elapsed < 1.0, f"100-file scan took {elapsed:.3f}s (budget 1s)"


def test_scan_live_cnoe_stacks_under_budget(repo_root: Path) -> None:
    target = repo_root / "cnoe-stacks"
    if not target.exists():
        pytest.skip("cnoe-stacks/ not present")
    start = timeit.default_timer()
    findings = scanner.scan([target], repo_root=repo_root)
    elapsed = timeit.default_timer() - start
    # Scan must be fast even with real files; soft findings are allowed.
    assert elapsed < 0.5, f"cnoe-stacks/ scan took {elapsed:.3f}s (budget 500ms)"
    assert scanner.hard_findings(findings) == [], (
        f"hard findings in cnoe-stacks/: {findings}"
    )
