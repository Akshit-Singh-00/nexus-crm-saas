import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("nexus_token");
  const wsId = localStorage.getItem("nexus_workspace_id");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (wsId) config.headers["X-Workspace-Id"] = wsId;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("nexus_token");
    }
    return Promise.reject(err);
  }
);

export default api;
