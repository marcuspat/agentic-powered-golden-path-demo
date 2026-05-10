# Tier 6 — UI (Playwright)

Placeholder for browser-driven tests. The agent currently has no UI;
this directory exists so that the tier system in ADR-0015 is complete
and so that the existing `playwright.config.ts` keeps working.

## Files

- `example.spec.ts` — sanity check that Playwright can run.

## Running

```bash
npm install
npm test            # runs Playwright
# or
npx playwright test tests/ui
```

## When to populate

Add specs here when the project gains a web UI (a future "Golden Path
console" is on the roadmap; see the ADR backlog).
