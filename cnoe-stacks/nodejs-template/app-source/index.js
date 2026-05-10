// {{ appName }} -- Golden Path Node.js service.
// Implements: HTTP server, JSON root, /healthz, /readyz, /metrics, OTel SDK init.
// See ADR-0020 for the observability contract this file satisfies.

'use strict';

const http = require('http');
const url = require('url');
const pkg = require('./package.json');

// ---------------------------------------------------------------------------
// OpenTelemetry SDK init (best-effort: never blocks server startup).
// ---------------------------------------------------------------------------
try {
  const { NodeSDK } = require('@opentelemetry/sdk-node');
  const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
  const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
  const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-http');
  const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
  const { resourceFromAttributes } = require('@opentelemetry/resources');
  const {
    ATTR_SERVICE_NAME,
    ATTR_SERVICE_VERSION,
  } = require('@opentelemetry/semantic-conventions');

  const otlpEndpoint =
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT ||
    'http://otel-collector.observability.svc.cluster.local:4318';

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || '{{ appName }}',
      [ATTR_SERVICE_VERSION]: pkg.version,
    }),
    traceExporter: new OTLPTraceExporter({ url: `${otlpEndpoint}/v1/traces` }),
    metricReader: new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({ url: `${otlpEndpoint}/v1/metrics` }),
    }),
    instrumentations: [getNodeAutoInstrumentations()],
  });

  sdk.start();
  process.on('SIGTERM', () => {
    sdk.shutdown().catch((err) => console.error('OTel shutdown failed', err));
  });
  console.log(`[otel] SDK started, exporting to ${otlpEndpoint}`);
} catch (err) {
  console.error('[otel] SDK init failed; continuing without telemetry:', err.message);
}

// ---------------------------------------------------------------------------
// Prometheus metrics.
// ---------------------------------------------------------------------------
const client = require('prom-client');
const register = client.register;
client.collectDefaultMetrics({ register });

const httpRequestsTotal = new client.Counter({
  name: 'http_requests_total',
  help: 'Count of HTTP requests handled by the service.',
  labelNames: ['method', 'route', 'status'],
  registers: [register],
});

// ---------------------------------------------------------------------------
// HTTP server.
// ---------------------------------------------------------------------------
const port = parseInt(process.env.PORT, 10) || 8080;
const appName = process.env.APP_NAME || '{{ appName }}';

function send(res, status, body, contentType = 'application/json') {
  res.statusCode = status;
  res.setHeader('Content-Type', contentType);
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
}

const server = http.createServer(async (req, res) => {
  const route = url.parse(req.url).pathname || '/';
  let status = 200;
  try {
    if (route === '/' && req.method === 'GET') {
      send(res, 200, {
        app: appName,
        message: `Hello from ${appName}!`,
        version: pkg.version,
      });
    } else if ((route === '/healthz' || route === '/readyz') && req.method === 'GET') {
      send(res, 200, { status: 'ok' });
    } else if (route === '/metrics' && req.method === 'GET') {
      const body = await register.metrics();
      send(res, 200, body, register.contentType);
    } else {
      status = 404;
      send(res, 404, { error: 'not found', route });
    }
  } catch (err) {
    status = 500;
    console.error('[http] handler error:', err);
    send(res, 500, { error: 'internal error' });
  } finally {
    httpRequestsTotal.labels(req.method || 'GET', route, String(status)).inc();
  }
});

server.listen(port, () => {
  console.log(`[http] ${appName} v${pkg.version} listening on :${port}`);
});

process.on('SIGTERM', () => {
  console.log('[http] SIGTERM received, shutting down');
  server.close(() => process.exit(0));
});

module.exports = server;
