# ADR-0020: Observe with Prometheus, Grafana, and OpenTelemetry

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Platform Engineering, SRE
- **Tags:** observability, metrics, logs, traces

## Context

The platform is responsible for two observability concerns:

- **Platform observability** — health of the cluster, ArgoCD, Tekton, ingress.
- **Application observability** — golden signals (latency, traffic, errors, saturation) of every onboarded application.

`docs/monitoring-observability-strategy.md` already sketches a stack but does not encode the decision crisply. This ADR codifies the choice and the contract that stack templates must satisfy so every onboarded application is observable on day one.

## Decision Drivers

- One stack covers both platform and app observability.
- Every onboarded app gets metrics, logs, and traces *automatically* by inheriting from the GitOps template.
- Cloud-native, open-source, vendor-neutral.
- Lightweight enough to run inside the demo KinD cluster.

## Considered Options

1. **Prometheus + Grafana + Loki + Tempo + OpenTelemetry Collector** (the "OSS LGTM"-adjacent stack).
2. **Datadog or New Relic** SaaS — out of scope; the demo is local.
3. **Roll-your-own with raw Kubernetes logs and `kubectl top`** — insufficient for golden signals.
4. **Elastic Stack (ELK)** — heavier; less Kubernetes-native than LGTM.

## Decision

We will adopt the open-source **LGTM-style stack**:

- **Prometheus** for metrics (already a dependency of ArgoCD and idpbuilder add-ons).
- **Grafana** for dashboards.
- **Loki** for logs.
- **Tempo** (or Jaeger) for traces.
- **OpenTelemetry Collector** as the single ingest point for app telemetry.

The stack templates (`cnoe-stacks/nodejs-template/`) ship with:

1. An OTel SDK initialised in `index.js` exporting to the in-cluster Collector via OTLP.
2. A `/metrics` endpoint exposing Prometheus metrics.
3. A `ServiceMonitor` (or `PodMonitor`) in `cnoe-stacks/nodejs-gitops-template/` so Prometheus auto-discovers the new app.
4. A standard Grafana dashboard JSON keyed by `app=<appName>` so every onboarded app gets the same dashboard.

The OTel Collector is installed by an idpbuilder add-on (or via a Helm chart in `config/monitoring/`).

## Consequences

### Positive

- Every onboarded application is observable from the moment ArgoCD finishes the first sync.
- One pane of glass (Grafana) for the entire cluster.
- Open-source stack; no vendor lock-in.
- OpenTelemetry future-proofs the choice of backend; we can swap Tempo for Jaeger or a SaaS without changing the SDK.

### Negative / Costs

- Memory footprint is significant on a developer laptop; the demo profile must run with reduced retention.
- Each new stack template (Python, Go) must implement the same OTel SDK contract.
- Dashboards must be maintained as code in `config/monitoring/`.

### Neutral

- The agent itself is not (yet) instrumented; agent runs are a CLI lifetime so there's little to observe. A future "agent as a service" profile would emit OTel traces of `run_onboarding_flow`.

## Compliance & Security Considerations

- Logs may contain PII or secrets if applications log them. Document a logging guideline; consider a Loki-side filter to redact known patterns (`Bearer …`, `password=…`).
- Grafana access control must be configured (anonymous role disabled, SSO for production).
- ServiceMonitor's scrape relies on Prometheus's RBAC; ensure it can read across onboarded namespaces (ADR-0017).

## Follow-up Work

- [ ] Install the OTel Collector + LGTM stack via a `config/monitoring/` Helm chart bundle.
- [ ] Add `index.js` OTel boilerplate to `cnoe-stacks/nodejs-template/app-source/`.
- [ ] Add `servicemonitor.yaml` to `cnoe-stacks/nodejs-gitops-template/`.
- [ ] Author the standard "Onboarded Application" Grafana dashboard JSON.
- [ ] Reconcile `docs/monitoring-observability-strategy.md` with this ADR.

## References

- ADR-0002 — idpbuilder add-on framework.
- ADR-0017 — Per-namespace deployments (drives ServiceMonitor namespace selectors).
- `docs/monitoring-observability-strategy.md` — older strategy doc.
- OpenTelemetry: <https://opentelemetry.io/>.
