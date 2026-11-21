import { buildUrl } from "./api";
import type { ComponentStatus, SystemEnginesResponse, SystemHealthSummary } from "@/types";

export async function getSystemEngines(baseUrl: string): Promise<SystemEnginesResponse | null> {
  try {
    const response = await fetch(buildUrl("/api/system/engines", baseUrl), {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) return null;
    return (await response.json()) as SystemEnginesResponse;
  } catch {
    return null;
  }
}

export function mapSystemHealth(
  payload: SystemEnginesResponse | null,
  backendConnected: boolean,
): SystemHealthSummary {
  if (!backendConnected || payload === null) {
    return {
      workspace: "disconnected",
      instantNgp: "disconnected",
      backend: "disconnected",
    };
  }

  const workspace: ComponentStatus = payload.workspace.found ? "ready" : "missing";

  let instantNgp: ComponentStatus = "missing";
  const ngp = payload.instant_ngp;
  if (ngp.ready) {
    instantNgp = "ready";
  } else if (ngp.installed && ngp.compiled === false) {
    instantNgp = "compiling";
  } else if (ngp.installed && ngp.python_bindings && !ngp.ready) {
    instantNgp = "unavailable";
  } else if (ngp.installed) {
    instantNgp = "unavailable";
  }

  const backend: ComponentStatus = payload.backend.ready ? "ready" : "unavailable";

  return { workspace, instantNgp, backend };
}

export interface PipelineConfigApi {
  source: string;
  camera_estimation: { camera_model: string; use_gpu: boolean; min_registration_ratio: number };
  training: { n_steps: number };
  mesh: { resolution: number; density_threshold: number };
  mesh_cleanup: Record<string, number>;
  export_formats: string[];
  stages_always_run: string[];
}

/** GET /api/system/config — read-only pipeline parameters (no host paths). */
export async function getPipelineConfig(baseUrl: string): Promise<PipelineConfigApi> {
  const response = await fetch(buildUrl("/api/system/config", baseUrl), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return (await response.json()) as PipelineConfigApi;
}
