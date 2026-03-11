import { trace } from "@opentelemetry/api";

type LogSeverity = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";

type LogFields = Record<string, unknown>;

const SERVICE_NAME = process.env.SERVICE_NAME ?? "terrier-connect-gateway";
const SERVICE_VERSION = process.env.SERVICE_VERSION ?? "";
const APP_ENV = process.env.APP_ENV ?? process.env.NODE_ENV ?? "development";
const GOOGLE_CLOUD_PROJECT = process.env.GOOGLE_CLOUD_PROJECT ?? "";

function traceFields(): LogFields {
  const span = trace.getActiveSpan();
  const context = span?.spanContext();
  if (!context) {
    return {};
  }

  const traceId = context.traceId;
  const spanId = context.spanId;
  const sampled = Boolean(context.traceFlags & 0x1);

  return {
    trace_id: traceId,
    span_id: spanId,
    trace_sampled: sampled,
    ...(GOOGLE_CLOUD_PROJECT
      ? {
          "logging.googleapis.com/trace": `projects/${GOOGLE_CLOUD_PROJECT}/traces/${traceId}`,
          "logging.googleapis.com/spanId": spanId,
          "logging.googleapis.com/trace_sampled": sampled,
        }
      : {}),
  };
}

function write(severity: LogSeverity, message: string, fields: LogFields = {}): void {
  const payload = {
    timestamp: new Date().toISOString(),
    severity,
    message,
    service: SERVICE_NAME,
    environment: APP_ENV,
    serviceContext: {
      service: SERVICE_NAME,
      ...(SERVICE_VERSION ? { version: SERVICE_VERSION } : {}),
    },
    ...traceFields(),
    ...fields,
  };

  const line = JSON.stringify(payload);
  if (severity === "ERROR" || severity === "CRITICAL") {
    console.error(line);
    return;
  }
  console.log(line);
}

function errorFields(error: unknown): LogFields {
  if (error instanceof Error) {
    return {
      error_name: error.name,
      error_message: error.message,
      error_stack: error.stack,
    };
  }
  return { error: String(error) };
}

export const logger = {
  debug(message: string, fields?: LogFields): void {
    write("DEBUG", message, fields);
  },
  info(message: string, fields?: LogFields): void {
    write("INFO", message, fields);
  },
  warn(message: string, fields?: LogFields): void {
    write("WARNING", message, fields);
  },
  error(message: string, error?: unknown, fields: LogFields = {}): void {
    write("ERROR", message, { ...fields, ...(error === undefined ? {} : errorFields(error)) });
  },
};
