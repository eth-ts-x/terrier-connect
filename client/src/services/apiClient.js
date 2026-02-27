import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || "/api";
const MEDIA_BASE_URL = process.env.REACT_APP_MEDIA_BASE_URL || API_BASE_URL;

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, // Send HttpOnly JWT cookies on every request
  headers: {
    "Content-Type": "application/json",
  },
});

// Response interceptor: redirect to /login on 401 (except for the login request itself)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const isLoginRequest = error.config?.url?.includes("/users/login");
    if (error.response?.status === 401 && !isLoginRequest) {
      // Let AuthContext handle the state reset; just navigate to login
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export const resolveMediaUrl = (path) => {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path; // absolute URL (e.g. GCS) — pass through
  if (path.startsWith("/")) return path; // root-relative — pass through
  return `${MEDIA_BASE_URL}/${path}`; // bare key (legacy) — prepend base
};

export default apiClient;
