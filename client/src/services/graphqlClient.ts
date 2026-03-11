import axios from "axios";

import { createRequestId } from "./requestId";

const GRAPHQL_URL = process.env.REACT_APP_GRAPHQL_URL || "/graphql";

const graphqlClient = axios.create({
  baseURL: GRAPHQL_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

graphqlClient.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers["X-Request-ID"] = createRequestId();
  return config;
});

const getGraphQLErrorMessage = (errors: Array<{ message?: string }> | undefined): string => {
  if (!Array.isArray(errors) || errors.length === 0) {
    return "GraphQL request failed.";
  }

  return errors.map((error) => error.message || "Unknown GraphQL error").join("; ");
};

export async function executeGraphQL<TData>(query: string, variables: Record<string, unknown> = {}): Promise<TData> {
  const response = await graphqlClient.post("", {
    query,
    variables,
  });

  if (response.data?.errors?.length) {
    throw new Error(getGraphQLErrorMessage(response.data.errors));
  }

  return response.data?.data as TData;
}

export default graphqlClient;
