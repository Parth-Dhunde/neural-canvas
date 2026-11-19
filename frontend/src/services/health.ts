import { API_ENDPOINTS } from "@/lib/constants";
import { buildUrl } from "./api";
import { getSystemEngines, mapSystemHealth } from "./system";
import type { BackendHealth } from "@/types";

interface HealthPayload {
  status: string;
}

interface VersionPayload {
  version: string;
  app?: string;
}

/**
 * Poll the backend liveness endpoint.
 *
 * GET /health — on success the frontend marks the backend as Connected.
 */
export async function healthCheck(baseUrl: string): Promise<BackendHealth> {
  const endpoints = [...API_ENDPOINTS];

  try {
    const response = await fetch(buildUrl("/health", baseUrl), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }

    const payload = (await response.json()) as HealthPayload;
    if (payload.status !== "ok") {
      throw new Error(`Unexpected health status: ${payload.status}`);
    }

    let apiVersion: string | null = null;
    let systemHealth = mapSystemHealth(null, true);
    try {
      const versionResponse = await fetch(buildUrl("/version", baseUrl), {
        method: "GET",
        headers: { Accept: "application/json" },
      });
      if (versionResponse.ok) {
        const versionPayload = (await versionResponse.json()) as VersionPayload;
        apiVersion = versionPayload.version ?? null;
      }
    } catch {
      // Version endpoint is optional for connectivity
    }

    const engines = await getSystemEngines(baseUrl);
    systemHealth = mapSystemHealth(engines, true);

    return {
      status: "connected",
      url: baseUrl,
      lastHeartbeat: new Date().toISOString(),
      apiVersion,
      endpoints,
      system: systemHealth,
    };
  } catch {
    return {
      status: "disconnected",
      url: baseUrl,
      lastHeartbeat: null,
      apiVersion: null,
      endpoints,
      system: mapSystemHealth(null, false),
    };
  }
}
