import { formatDuration } from "@/lib/dashboardStats";
import type { EngineId, Job, JobStatus, TrainingMetrics } from "@/types";

export interface TrainingMetricsApi {
  final_loss?: number | null;
  last_logged_step?: number | null;
  total_steps?: number | null;
  mean_steps_per_second?: number | null;
  checkpoint_count?: number | null;
  peak_vram_mib?: number | null;
  source?: string | null;
}

export interface JobApiResponse {
  id: string;
  name: string;
  engine: string;
  job_type?: string;
  status: string;
  progress: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  training_duration_seconds?: number | null;
  pipeline_duration_seconds?: number | null;
  training_metrics?: TrainingMetricsApi | null;
  psnr_db?: number | null;
  failed_stage?: { id: number; name: string } | null;
  last_error?: string | null;
  outputs?: { mesh?: boolean; cleaned_mesh?: boolean; exports?: Record<string, string[]> };
  image_count?: number;
  uploaded_at?: string | null;
  image_filenames?: string[];
  mesh_path?: string | null;
  mesh_cleanup?: { status?: string } | null;
  vertex_count?: number;
  triangle_count?: number;
}

export interface JobListApiResponse {
  jobs: JobApiResponse[];
  total: number;
}

export interface UploadApiResponse {
  job_id: string;
  uploaded: string[];
  image_count: number;
  uploaded_at: string;
  previews: string[];
}

function num(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function mapTrainingMetrics(
  api: TrainingMetricsApi | null | undefined,
): TrainingMetrics | null {
  if (!api) return null;
  return {
    finalLoss: num(api.final_loss),
    lastLoggedStep: num(api.last_logged_step),
    totalSteps: num(api.total_steps),
    meanStepsPerSecond: num(api.mean_steps_per_second),
    checkpointCount: num(api.checkpoint_count),
    peakVramMib: num(api.peak_vram_mib),
    source: api.source ?? null,
  };
}

export function mapJobFromApi(api: JobApiResponse): Job {
  const trainingSeconds = num(api.training_duration_seconds);
  return {
    id: api.id,
    name: api.name,
    engine: api.engine as EngineId,
    jobType: api.job_type ?? "image_to_3d",
    status: api.status as JobStatus,
    progress: api.progress,
    createdAt: api.created_at,
    startedAt: api.started_at ?? null,
    completedAt: api.completed_at ?? null,
    trainingDurationSeconds: trainingSeconds,
    pipelineDurationSeconds: num(api.pipeline_duration_seconds),
    trainingMetrics: mapTrainingMetrics(api.training_metrics),
    psnrDb: num(api.psnr_db),
    failedStage: api.failed_stage ?? null,
    lastError: api.last_error ?? null,
    jobOutputs: {
      mesh: api.outputs?.mesh ?? false,
      cleanedMesh: api.outputs?.cleaned_mesh ?? false,
      exports: api.outputs?.exports ?? {},
    },
    duration: trainingSeconds !== null ? formatDuration(trainingSeconds) : undefined,
    imageCount: api.image_count ?? 0,
    uploadedAt: api.uploaded_at ?? null,
    imageFilenames: api.image_filenames ?? [],
    meshPath: api.mesh_path ?? null,
    meshCleanupStatus: api.mesh_cleanup?.status ?? null,
    vertexCount: api.vertex_count ?? 0,
    triangleCount: api.triangle_count ?? 0,
    images: api.image_count ?? 0,
    logs: [],
    outputs: [],
    metrics: [],
  };
}

export function previewFilenameForOriginal(original: string): string {
  const stem = original.replace(/\.[^.]+$/, "");
  return `${stem}_preview.jpg`;
}

export function buildPreviewUrl(jobId: string, previewFilename: string, baseUrl: string): string {
  const root = baseUrl.replace(/\/$/, "");
  return `${root}/api/jobs/${jobId}/preview/${encodeURIComponent(previewFilename)}`;
}
