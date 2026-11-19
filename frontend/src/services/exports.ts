import { apiFetch } from "./api";

export type MeshVariant = "cleaned" | "original";
export type MeshFormat = "glb" | "obj" | "ply";

export interface ExportFileApi {
  path: string | null;
  available: boolean;
  bytes: number;
  url?: string;
  problem?: string;
}

export interface ExportVariantApi {
  source: string;
  formats: Partial<Record<MeshFormat, ExportFileApi>>;
  complete: boolean;
  cleanup_id?: string | null;
  unavailable_reason?: string | null;
}

/** GET /api/jobs/{id}/exports — verified against files on disk by the backend. */
export interface ExportManifestApi {
  job_id: string;
  preferred: MeshVariant | null;
  viewer_url: string | null;
  variants: Record<MeshVariant, ExportVariantApi>;
}

export async function getJobExports(jobId: string, baseUrl?: string): Promise<ExportManifestApi> {
  return apiFetch<ExportManifestApi>(`/api/jobs/${encodeURIComponent(jobId)}/exports`, {
    baseUrl,
  });
}
