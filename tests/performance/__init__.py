"""Tier 4 — performance benchmarks.

Measures latencies; asserts only on regressions, never on absolute time.
Uses ``pytest-benchmark`` if installed, else falls back to ``timeit``.
"""
