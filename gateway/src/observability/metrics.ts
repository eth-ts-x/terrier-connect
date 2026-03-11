import { Counter, Histogram, Registry, collectDefaultMetrics } from "prom-client";
import type { Request, Response } from "express";

export const metricsRegistry = new Registry();

collectDefaultMetrics({
  prefix: "gateway_",
  register: metricsRegistry,
});

const httpRequestsTotal = new Counter({
  name: "gateway_http_requests_total",
  help: "Total number of HTTP requests handled by the gateway.",
  labelNames: ["method", "route", "status_code"],
  registers: [metricsRegistry],
});

const httpRequestDurationSeconds = new Histogram({
  name: "gateway_http_request_duration_seconds",
  help: "HTTP request duration in seconds for the gateway.",
  labelNames: ["method", "route", "status_code"],
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
  registers: [metricsRegistry],
});

export function observeHttpRequest(args: {
  method: string;
  route: string;
  statusCode: number;
  durationSeconds: number;
}): void {
  const labels = {
    method: args.method,
    route: args.route,
    status_code: String(args.statusCode),
  };

  httpRequestsTotal.inc(labels);
  httpRequestDurationSeconds.observe(labels, args.durationSeconds);
}

export async function metricsHandler(_req: Request, res: Response): Promise<void> {
  res.setHeader("Content-Type", metricsRegistry.contentType);
  res.end(await metricsRegistry.metrics());
}
