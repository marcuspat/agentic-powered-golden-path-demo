# Tier 4 — Performance

Micro-benchmarks for the agent's hot paths. Per ADR-0015 these run weekly
in CI; locally, invoke with `make bench` or `pytest tests/performance -q`.

## Why no absolute-time assertions?

Container CI runners vary by an order of magnitude in CPU. Asserting on
"X must complete in Y seconds" produces flaky tests. Instead each bench
asserts only against a *generous* upper bound (e.g. 50 ms when the
typical run is sub-millisecond) so that a 100x regression — the only
kind worth alerting on — fails loudly while normal runner jitter does
not.

For trend tracking use `pytest-benchmark`'s comparison features:

```bash
pytest tests/performance --benchmark-autosave
pytest tests/performance --benchmark-compare
```

## Files

- `bench_intent_extraction.py` — regex fallback path of `IntentExtractionService`.
- `bench_template_rendering.py` — Jinja2 render of the `nodejs-template` stack.
- `test_legacy_performance.py` — older perf harness, marked `legacy`.

## Required tools

- `pytest-benchmark` (optional; benchmarks fall back to `timeit` if missing).
- `psutil` (only the legacy harness; auto-skipped if absent).
