import { API_ENDPOINTS, DEFAULT_BACKEND_URL } from "@/lib/constants";
import type { BackendHealth } from "@/types";

export const PLACEHOLDER_BACKEND_HEALTH: BackendHealth = {
  status: "disconnected",
  url: DEFAULT_BACKEND_URL,
  lastHeartbeat: null,
  apiVersion: null,
  endpoints: [...API_ENDPOINTS],
};
