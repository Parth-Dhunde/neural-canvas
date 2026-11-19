import { PIPELINE_STEP_NAMES } from "@/lib/constants";
import { mapPipelineFromApi, type PipelineApiResponse } from "@/lib/mapPipeline";
import type { PipelineStep } from "@/types";

export function createInitialPipeline(): PipelineStep[] {
  return PIPELINE_STEP_NAMES.map((name, index) => ({
    id: index + 1,
    name,
    status: "waiting" as const,
    progress: 0,
    duration: "—",
    logs: [],
  }));
}

/** Pipeline state after a successful image upload. */
export function pipelineAfterUpload(): PipelineStep[] {
  const steps = createInitialPipeline();
  steps[0] = {
    ...steps[0],
    status: "completed",
    progress: 100,
    duration: "—",
  };
  return steps;
}

export function pipelineFromApi(api: PipelineApiResponse): PipelineStep[] {
  if (!api.stages.length) {
    return createInitialPipeline();
  }
  return mapPipelineFromApi(api);
}

export function pipelineForJob(imageCount: number): PipelineStep[] {
  return imageCount > 0 ? pipelineAfterUpload() : createInitialPipeline();
}

export function backgroundRemovalStage(pipeline: PipelineStep[]): PipelineStep | undefined {
  return pipeline.find((step) => step.id === 2);
}

export function cameraEstimationStage(pipeline: PipelineStep[]): PipelineStep | undefined {
  return pipeline.find((step) => step.id === 3);
}

export function reconstructionStage(pipeline: PipelineStep[]): PipelineStep | undefined {
  return pipeline.find((step) => step.id === 4);
}

export function canRunBackgroundRemoval(pipeline: PipelineStep[], imageCount: number): boolean {
  if (imageCount <= 0) return false;
  const uploadDone = pipeline[0]?.status === "completed";
  const removal = backgroundRemovalStage(pipeline);
  return uploadDone && (removal?.status === "waiting" || removal?.status === "queued");
}

/** True when the next implemented pipeline stage can be started. */
function isPendingStage(status: PipelineStep["status"] | undefined): boolean {
  return status === "waiting" || status === "queued" || status === "failed";
}

/** Next stage that can start or be retried after failure. */
export function findNextRunnableStage(pipeline: PipelineStep[]): PipelineStep | undefined {
  for (const step of pipeline) {
    if (step.status === "completed") {
      continue;
    }
    if (isPendingStage(step.status)) {
      return step;
    }
    return undefined;
  }
  return undefined;
}

export function canStartPipeline(pipeline: PipelineStep[], imageCount: number): boolean {
  if (imageCount <= 0) return false;

  const next = findNextRunnableStage(pipeline);
  if (!next) return false;

  const backgroundRemoval = backgroundRemovalStage(pipeline);
  if (next.id === 2) {
    return pipeline[0]?.status === "completed";
  }

  const cameraEstimation = cameraEstimationStage(pipeline);
  if (next.id === 3) {
    return backgroundRemoval?.status === "completed";
  }

  const reconstruction = reconstructionStage(pipeline);
  if (next.id === 4) {
    return cameraEstimation?.status === "completed";
  }

  if (next.id === 5) {
    return reconstruction?.status === "completed";
  }

  return isPendingStage(next.status);
}
