import type { EngineId } from "@/types";

export const APP_NAME = "NeuralCanvas";
export const APP_SUBTITLE = "Multi-view 3D reconstruction";
/** One-sentence description used in page metadata and Settings → About. */
export const APP_DESCRIPTION =
  "NeuralCanvas reconstructs a coloured 3D mesh from photographs of an object, using COLMAP and Instant-NGP on your own machine.";

export const SUPPORTED_ENGINES: EngineId[] = ["Instant-NGP"];

// `import.meta.env` is undefined outside Vite (unit tests), hence the optional chain.
export const DEFAULT_BACKEND_URL = import.meta.env?.VITE_BACKEND_URL ?? "http://localhost:8000";

export const PIPELINE_STEP_NAMES = [
  "Upload",
  "Background Removal",
  "Camera Estimation",
  "Reconstruction",
  "Mesh Generation",
  "Mesh Cleanup",
  "Export",
] as const;

/** Main backend routes, listed in the connection popover. The full list is at /docs. */
export const API_ENDPOINTS = [
  "GET /health",
  "GET /version",
  "GET /api/system/engines",
  "GET /api/system/config",
  "GET /api/hardware",
  "GET /api/dashboard/summary",
  "POST /api/jobs",
  "GET /api/jobs",
  "GET /api/jobs/{id}",
  "DELETE /api/jobs/{id}",
  "POST /api/jobs/bulk-delete",
  "POST /api/jobs/{id}/upload",
  "GET /api/jobs/{id}/pipeline",
  "POST /api/jobs/{id}/pipeline/start",
  "POST /api/jobs/{id}/pipeline/stages/{n}/run",
  "POST /api/jobs/{id}/pipeline/pause",
  "POST /api/jobs/{id}/pipeline/resume",
  "POST /api/jobs/{id}/pipeline/cancel",
  "GET /api/jobs/{id}/logs",
  "GET /api/jobs/{id}/mesh",
  "GET /api/jobs/{id}/exports",
] as const;

export const HARDWARE_HELPER_MESSAGE =
  "Live telemetry refreshes every 1.5s while the dashboard is open.";

/** Shown only while the backend is confirmed offline. */
export const OWNER_CONTACT_EMAIL = "parth.jd.261105@gmail.com";
