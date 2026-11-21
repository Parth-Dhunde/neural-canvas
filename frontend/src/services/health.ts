import { API_ENDPOINTS } from "@/lib/constants";
import { HEALTH_TIMING } from "@/lib/backendStatus";
import { buildUrl } from "./api";
import { getSystemEngines, mapSystemHealth } from "./system";
import type { BackendHealth } from "@/types";

/** GET /health with a timeout. True only for a 2xx response with `{"status": "ok"}`. */
export async function pingHealth(
  baseUrl: string,
  timeoutMs: number = HEALTH_TIMING.requestTimeoutMs,
): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(buildUrl("/health", baseUrl), {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) return false;
    const payload = (await response.json()) as { status?: string };
    return payload.status === "ok";
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/** Version and engine readiness, fetched once when the backend becomes reachable. */
export async function fetchBackendDetails(
  baseUrl: string,
): Promise<Pick<BackendHealth, "apiVersion" | "system">> {
  let apiVersion: string | null = null;
  try {
    const response = await fetch(buildUrl("/version", baseUrl), {
      headers: { Accept: "application/json" },
    });
    if (response.ok) apiVersion = ((await response.json()) as { version?: string }).version ?? null;
  } catch {
    // Version is informational only.
  }
  const engines = await getSystemEngines(baseUrl);
  return { apiVersion, system: mapSystemHealth(engines, true) };
}

export function offlineHealth(baseUrl: string): BackendHealth {
  return {
    status: "disconnected",
    url: baseUrl,
    lastHeartbeat: null,
    apiVersion: null,
    endpoints: [...API_ENDPOINTS],
    system: mapSystemHealth(null, false),
  };
}
