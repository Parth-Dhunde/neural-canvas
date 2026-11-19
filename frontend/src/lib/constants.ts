import type { EngineId } from "@/types";

export const APP_NAME = "NeuralCanvas";
export const APP_SUBTITLE = "AI-Powered 3D Reconstruction Platform";

export const SUPPORTED_ENGINES: EngineId[] = ["Instant-NGP"];

export const DEFAULT_BACKEND_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export const PIPELINE_STEP_NAMES = [
  "Upload",
  "Background Removal",
  "Camera Estimation",
  "Reconstruction",
  "Mesh Generation",
  "Mesh Cleanup",
  "Export",
] as const;

export const API_ENDPOINTS = [
  "GET /health",
  "GET /version",
  "POST /api/jobs",
  "GET /api/jobs",
  "GET /api/jobs/{id}",
  "POST /api/jobs/{id}/upload",
  "POST /api/jobs/{id}/pipeline/start",
  "POST /api/jobs/{id}/pipeline/pause",
  "POST /api/jobs/{id}/pipeline/cancel",
  "GET /api/jobs/{id}/logs",
  "GET /api/hardware",
  "GET /api/jobs/{id}/hardware",
  "GET /api/jobs/{id}/mesh",
  "GET /api/system/engines",
] as const;

export const HARDWARE_HELPER_MESSAGE =
  "Live telemetry refreshes every 1.5s while the dashboard is open.";
