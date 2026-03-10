import { ApolloServer } from "@apollo/server";
import { expressMiddleware } from "@apollo/server/express4";
import DataLoader from "dataloader";
import cors from "cors";
import express, { type Request, type Response } from "express";
import helmet from "helmet";

import {
  DjangoAPI,
  type GatewayLikeStatus,
  type GatewayUser,
} from "./datasources/DjangoAPI.js";
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

function headerValue(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value.join("; ") : (value ?? "");
}

function createContext(req: Request, res: Response): AppContext {
  const djangoAPI = new DjangoAPI({
    baseURL: `${DJANGO_API_URL}/api/`,
    authorization: headerValue(req.headers.authorization),
    cookie: headerValue(req.headers.cookie),
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

  const server = new ApolloServer<AppContext>({
    typeDefs,
    resolvers,
    introspection: process.env.NODE_ENV !== "production",
  });

  await server.start();

  app.get("/healthz", (_req, res) => {
    res.json({ status: "ok", service: "graphql-gateway" });
  });

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
    console.log(`🚀 GraphQL Gateway ready at http://0.0.0.0:${PORT}/graphql`);
  });
}

main().catch((error) => {
  console.error("Gateway failed to start:", error);
  process.exit(1);
});
