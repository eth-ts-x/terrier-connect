import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "/api";
const MEDIA_BASE_URL = process.env.REACT_APP_MEDIA_BASE_URL || API_BASE_URL;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers = {
        ...config.headers,
        Authorization: token,
      };
    }
    return config;
  },
  (error) => Promise.reject(error)
);

export const resolveMediaUrl = (path) => {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;  // absolute URL (e.g. GCS) — pass through
  if (path.startsWith("/")) return path;          // already a root-relative path — pass through
  return `${MEDIA_BASE_URL}/${path}`;             // bare key (legacy fallback) — prepend base
};

export default apiClient;