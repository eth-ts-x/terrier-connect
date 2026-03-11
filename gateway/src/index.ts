import { ApolloServer } from "@apollo/server";
import { expressMiddleware } from "@apollo/server/express4";
import { randomUUID } from "node:crypto";
import DataLoader from "dataloader";
import cors from "cors";
import express, { type Request, type Response } from "express";
import helmet from "helmet";

import {
  DjangoAPI,
  type GatewayLikeStatus,
  type GatewayUser,
} from "./datasources/DjangoAPI.js";
import { logger } from "./observability/logger.js";
import { metricsHandler, observeHttpRequest } from "./observability/metrics.js";
import { resolvers } from "./resolvers/index.js";
import { typeDefs } from "./schema/index.js";

interface AppContext {
  req: Request;
  res: Response;
  dataSources: {
    djangoAPI: DjangoAPI;
  };
  loaders: {
    userById: DataLoader<number, GatewayUser>;
    likeStatusByPostId: DataLoader<string, GatewayLikeStatus>;
  };
}

const PORT = Number.parseInt(process.env.PORT ?? "4000", 10);
const DJANGO_API_URL = process.env.DJANGO_API_URL ?? "http://server:8000";
const CORS_ORIGIN = (process.env.CORS_ORIGIN ?? "http://localhost:3002")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);
const REQUEST_ID_HEADER = "x-request-id";
const IGNORED_OBSERVABILITY_PATHS = new Set(["/healthz", "/metrics"]);

function headerValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value.join("; ") : (value ?? "");
}

function requestIdFrom(req: Request): string {
  return headerValue(req.headers[REQUEST_ID_HEADER]) || randomUUID();
}

function createContext(req: Request, res: Response): AppContext {
  const djangoAPI = new DjangoAPI({
    baseURL: `${DJANGO_API_URL}/api/`,
    authorization: headerValue(req.headers.authorization),
    cookie: headerValue(req.headers.cookie),
    xRequestId: headerValue(req.headers[REQUEST_ID_HEADER]),
    traceparent: headerValue(req.headers.traceparent),
  });

  return {
    req,
    res,
    dataSources: {
      djangoAPI,
    },
    loaders: {
      userById: new DataLoader(async (userIds) => {
        return Promise.all(userIds.map((userId) => djangoAPI.getUser(userId)));
      }),
      likeStatusByPostId: new DataLoader(async (postIds) => {
        return Promise.all(postIds.map((postId) => djangoAPI.getLikeStatus(postId)));
      }),
    },
  };
}

async function main(): Promise<void> {
  const app = express();
  app.use(helmet({ contentSecurityPolicy: false }));
  app.use((req, res, next) => {
    const requestId = requestIdFrom(req);
    const start = process.hrtime.bigint();

    req.headers[REQUEST_ID_HEADER] = requestId;
    res.setHeader("X-Request-ID", requestId);

    res.on("finish", () => {
      if (IGNORED_OBSERVABILITY_PATHS.has(req.path)) {
        return;
      }

      const durationSeconds = Number(process.hrtime.bigint() - start) / 1_000_000_000;
      observeHttpRequest({
        method: req.method,
        route: req.path,
        statusCode: res.statusCode,
        durationSeconds,
      });
      logger.info("request completed", {
        request_id: requestId,
        method: req.method,
        path: req.path,
        status_code: res.statusCode,
        duration_ms: Math.round(durationSeconds * 1000 * 100) / 100,
      });
    });

    next();
  });

  const server = new ApolloServer<AppContext>({
    typeDefs,
    resolvers,
    introspection: process.env.NODE_ENV !== "production",
  });

  await server.start();

  app.get("/healthz", (_req, res) => {
    res.json({ status: "ok", service: "graphql-gateway" });
  });
  app.get("/metrics", metricsHandler);

  app.use(
    "/graphql",
    cors({
      origin: CORS_ORIGIN,
      credentials: true,
    }),
    express.json(),
    expressMiddleware(server, {
      context: async ({ req, res }) => createContext(req, res),
    }),
  );

  app.listen(PORT, () => {
    logger.info("gateway started", {
      port: PORT,
      graphql_path: "/graphql",
      health_path: "/healthz",
      metrics_path: "/metrics",
    });
  });
}

main().catch((error) => {
  logger.error("gateway failed to start", error);
  process.exit(1);
});
