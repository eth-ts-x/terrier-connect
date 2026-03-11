import axios from "axios";

import { createRequestId } from "./requestId";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "/api";
const MEDIA_BASE_URL = process.env.REACT_APP_MEDIA_BASE_URL || API_BASE_URL;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers["X-Request-ID"] = createRequestId();
  return config;
});

// Redirect to login on 401
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.includes("/login")) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export function resolveMediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/")) return path;
  return `${MEDIA_BASE_URL}/${path}`;
}

export default apiClient;
