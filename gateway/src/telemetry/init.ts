import type { IncomingMessage } from "node:http";

import { DiagConsoleLogger, DiagLogLevel, diag } from "@opentelemetry/api";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { NodeSDK } from "@opentelemetry/sdk-node";
import { GoogleAuth, type AuthClient } from "google-auth-library";

const IGNORED_INCOMING_PATHS = new Set(["/healthz", "/metrics"]);

function envFlag(name: string, defaultValue = false): boolean {
  const value = process.env[name];
  if (value === undefined) {
    return defaultValue;
  }

  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

function resolveTracesEndpoint(): string {
  const endpoint =
    process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?.trim() ||
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT?.trim() ||
    "";

  if (!endpoint) {
    return "";
  }

  return endpoint.endsWith("/v1/traces") ? endpoint : `${endpoint.replace(/\/$/, "")}/v1/traces`;
}

function parseHeaders(rawHeaders: string | undefined): Record<string, string> {
  if (!rawHeaders) {
    return {};
  }

  return rawHeaders.split(",").reduce<Record<string, string>>((headers, item) => {
    const [name, ...rest] = item.split("=");
    const value = rest.join("=");
    if (name?.trim() && value.trim()) {
      headers[name.trim()] = value.trim();
    }
    return headers;
  }, {});
}

function toHeaderRecord(headers: Headers | Record<string, string>): Record<string, string> {
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }
  return { ...headers };
}

async function getAuthenticatedClient(): Promise<AuthClient> {
  const auth = new GoogleAuth({
    scopes: "https://www.googleapis.com/auth/cloud-platform",
  });
  return auth.getClient();
}

async function createTraceExporter(): Promise<OTLPTraceExporter | undefined> {
  const url = resolveTracesEndpoint();
  if (!url) {
    return undefined;
  }

  const headers = parseHeaders(process.env.OTEL_EXPORTER_OTLP_HEADERS);
  if (envFlag("OTEL_EXPORTER_OTLP_GCP_AUTH")) {
    const authenticatedClient = await getAuthenticatedClient();
    return new OTLPTraceExporter({
      url,
      headers: {
        ...headers,
        ...toHeaderRecord(await authenticatedClient.getRequestHeaders()),
      },
    });
  }

  return new OTLPTraceExporter({
    url,
    headers: Object.keys(headers).length > 0 ? headers : undefined,
  });
}

async function initializeTelemetry(): Promise<void> {
  if (!envFlag("OTEL_TRACES_ENABLED")) {
    return;
  }

  const traceExporter = await createTraceExporter();
  if (!traceExporter) {
    return;
  }

  if (process.env.OTEL_LOG_LEVEL?.toLowerCase() === "debug") {
    diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);
  }

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      "service.name": process.env.SERVICE_NAME ?? "terrier-connect-gateway",
      "service.version": process.env.SERVICE_VERSION ?? "",
      "deployment.environment": process.env.APP_ENV ?? process.env.NODE_ENV ?? "development",
      ...(process.env.GOOGLE_CLOUD_PROJECT
        ? { "gcp.project_id": process.env.GOOGLE_CLOUD_PROJECT }
        : {}),
    }),
    traceExporter,
    instrumentations: [
      getNodeAutoInstrumentations({
        "@opentelemetry/instrumentation-fs": {
          enabled: false,
        },
        "@opentelemetry/instrumentation-http": {
          ignoreIncomingRequestHook: (request: IncomingMessage) => {
            const path = request.url?.split("?")[0] ?? "";
            return IGNORED_INCOMING_PATHS.has(path);
          },
        },
      }),
    ],
  });

  await sdk.start();

  const shutdown = async () => {
    await sdk.shutdown();
  };

  process.once("SIGTERM", () => {
    void shutdown();
  });
  process.once("SIGINT", () => {
    void shutdown();
  });
}

await initializeTelemetry();