import {
  mapExecutionFromApi,
  mapPipelineFromApi,
  type PipelineApiResponse,
} from "@/lib/mapPipeline";
import { createInitialPipeline } from "@/lib/pipeline";
import { apiFetch } from "./api";
import type { PipelineExecution, PipelineStep } from "@/types";

export interface PipelineStartApiResponse {
  job_id: string;
  stages_run: number[];
  logs: string[];
  stopped_reason: string;
  processed?: number;
  failed?: number;
  total?: number;
}

/** GET /api/jobs/{id}/pipeline */
export async function getPipeline(jobId: string, baseUrl?: string): Promise<PipelineStep[]> {
  try {
    const data = await apiFetch<PipelineApiResponse>(`/api/jobs/${jobId}/pipeline`, {
      baseUrl,
    });
    return mapPipelineFromApi(data);
  } catch {
    return createInitialPipeline();
  }
}

/** GET /api/jobs/{id}/pipeline — unlike getPipeline, errors are thrown to the caller. */
export async function getPipelineSnapshot(
  jobId: string,
  baseUrl?: string,
): Promise<{ steps: PipelineStep[]; execution: PipelineExecution | null }> {
  const data = await apiFetch<PipelineApiResponse>(`/api/jobs/${jobId}/pipeline`, { baseUrl });
  return { steps: mapPipelineFromApi(data), execution: mapExecutionFromApi(data) };
}

/** POST /api/jobs/{id}/pipeline/start */
export async function startPipeline(
  jobId: string,
  baseUrl?: string,
): Promise<PipelineStartApiResponse> {
  return apiFetch<PipelineStartApiResponse>(`/api/jobs/${jobId}/pipeline/start`, {
    method: "POST",
    baseUrl,
  });
}

/** POST /api/jobs/{id}/pipeline/pause */
export async function pausePipeline(jobId: string, baseUrl?: string): Promise<PipelineApiResponse> {
  return apiFetch<PipelineApiResponse>(`/api/jobs/${jobId}/pipeline/pause`, {
    method: "POST",
    baseUrl,
  });
}

/** POST /api/jobs/{id}/pipeline/cancel */
export async function cancelPipeline(
  jobId: string,
  baseUrl?: string,
): Promise<PipelineApiResponse> {
  return apiFetch<PipelineApiResponse>(`/api/jobs/${jobId}/pipeline/cancel`, {
    method: "POST",
    baseUrl,
  });
}
