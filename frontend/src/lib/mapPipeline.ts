import type { PipelineExecution, PipelineStep, PipelineStepStatus } from "@/types";

export interface PipelineStageApi {
  id: number;
  name: string;
  status: string;
  progress: number;
  completed_at: string | null;
}

export interface PipelineExecutionApi {
  status: string;
  current_stage_id: number | null;
  last_error: string | null;
}

export interface PipelineApiResponse {
  stages: PipelineStageApi[];
  execution?: PipelineExecutionApi | null;
}

export function mapExecutionFromApi(api: PipelineApiResponse): PipelineExecution | null {
  if (!api.execution) return null;
  const status = api.execution.status;
  return {
    status: status === "running" || status === "paused" || status === "cancelled" ? status : "idle",
    currentStageId: api.execution.current_stage_id,
    lastError: api.execution.last_error,
  };
}

export function mapPipelineFromApi(api: PipelineApiResponse): PipelineStep[] {
  return api.stages.map((stage) => ({
    id: stage.id,
    name: stage.name,
    status: stage.status as PipelineStepStatus,
    progress: stage.progress,
    duration: "—",
    logs: [],
  }));
}
