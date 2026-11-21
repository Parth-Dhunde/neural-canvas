import { toast } from "sonner";
import { engineOption, isSubmittableEngine } from "@/lib/engines";
import { mapExecutionFromApi, mapPipelineFromApi } from "@/lib/mapPipeline";
import { canStartPipeline, findNextRunnableStage, pipelineForJob } from "@/lib/pipeline";
import { chunkUploadFiles, validateUploadFiles } from "@/lib/uploadLimits";
import {
  createJob,
  deleteJobs,
  getJob,
  getJobs,
  uploadImages,
  type JobDeleteOutcome,
} from "@/services/jobs";
import { cancelPipeline, getPipeline, pausePipeline, startPipeline } from "@/services/pipeline";
import { useAppStore } from "@/store/useAppStore";
import type { BackendConnectionStatus, Job, LogEntry, PipelineStep } from "@/types";

/** Why backend-dependent actions are unavailable for `status`, or null if they are available.
 * Components pass the status from their store hook so server and client render the same. */
export function backendUnavailableReasonFor(status: BackendConnectionStatus): string | null {
  if (status === "connected") return null;
  if (status === "connecting") return "Checking the backend connection — try again in a moment.";
  return "The local backend is offline, so this action is unavailable.";
}

/** Same as `backendUnavailableReasonFor`, for the live store state (actions, not rendering). */
export function backendUnavailableReason(): string | null {
  return backendUnavailableReasonFor(useAppStore.getState().backendHealth.status);
}

/** Returns false (and explains why) when the backend cannot be used for `action`. */
function requireBackend(action: string): boolean {
  const reason = backendUnavailableReason();
  if (!reason) return true;
  toast.error(`Cannot ${action}`, { description: reason });
  appendLine({ level: "error", msg: `Cannot ${action}: ${reason}` });
  return false;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

function terminalTime(): string {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

function appendLine(line: Omit<LogEntry, "time"> & { time?: string }) {
  useAppStore.getState().appendTerminalLine({
    ...line,
    time: line.time ?? terminalTime(),
  });
}

async function loadPipelineForJob(job: Job | null): Promise<PipelineStep[]> {
  if (!job) {
    return pipelineForJob(0);
  }
  const { settings } = useAppStore.getState();
  return getPipeline(job.id, settings.backendUrl);
}

function replaceJobInStore(job: Job) {
  const { jobs, currentJob } = useAppStore.getState();
  const nextJobs = jobs.map((entry) => (entry.id === job.id ? job : entry));
  useAppStore.getState().setJobs(nextJobs);
  if (currentJob?.id === job.id) {
    useAppStore.getState().setCurrentJob(job);
  }
}

async function refreshCurrentJobPipeline(job: Job) {
  const pipeline = await loadPipelineForJob(job);
  const { currentJob } = useAppStore.getState();
  if (currentJob?.id === job.id) {
    useAppStore.getState().setPipeline(pipeline);
  }
}

/** Create a job via POST /api/jobs and update global state. */
export async function createNewJob(): Promise<Job | null> {
  const { settings, selectedEngine } = useAppStore.getState();

  if (!isSubmittableEngine(selectedEngine)) {
    const option = engineOption(selectedEngine);
    toast.error(`${selectedEngine} is not available yet`, { description: option?.description });
    return null;
  }
  if (!requireBackend("create a job")) return null;

  appendLine({ level: "info", msg: "Creating job..." });

  try {
    const job = await createJob({ engine: selectedEngine }, settings.backendUrl);
    useAppStore.getState().addJob(job);
    const pipeline = await loadPipelineForJob(job);
    useAppStore.getState().setPipeline(pipeline);
    appendLine({ level: "ok", msg: "Job created." });
    appendLine({ level: "info", msg: `Job ID: ${job.id}` });
    toast.success(`Created ${job.id}`);
    return job;
  } catch (error) {
    const message = errorMessage(error);
    appendLine({ level: "error", msg: `Failed to create job: ${message}` });
    toast.error("Could not create the job", { description: message });
    return null;
  }
}

export interface DeleteJobsSummary {
  deleted: string[];
  problems: JobDeleteOutcome[];
}

/**
 * Delete jobs on the backend and remove them from every view. Jobs the backend no longer has
 * are removed too; refused or failed ones stay and are reported.
 */
export async function deleteJobsById(ids: string[]): Promise<DeleteJobsSummary> {
  if (ids.length === 0) return { deleted: [], problems: [] };
  const reason = backendUnavailableReason();
  if (reason) throw new Error(reason);
  const { settings } = useAppStore.getState();
  const outcomes = await deleteJobs(ids, settings.backendUrl);
  const gone = outcomes.filter((o) => o.status === "deleted" || o.status === "not_found");
  const goneIds = gone.map((o) => o.job_id);
  const { currentJobChanged } = useAppStore.getState().removeJobs(goneIds);
  if (currentJobChanged) {
    useAppStore.getState().removeJobTerminalLines();
    const next = useAppStore.getState().currentJob;
    if (next) {
      const pipeline = await loadPipelineForJob(next);
      if (useAppStore.getState().currentJob?.id === next.id) {
        useAppStore.getState().setPipeline(pipeline);
      }
    }
  }
  goneIds.forEach((id) => appendLine({ level: "ok", msg: `Deleted ${id}.` }));
  const problems = outcomes.filter((o) => o.status === "refused" || o.status === "failed");
  problems.forEach((o) =>
    appendLine({ level: "error", msg: `Not deleted ${o.job_id}: ${o.detail ?? o.status}` }),
  );
  void refreshJobList();
  return { deleted: goneIds, problems };
}

async function applyControlResponse(
  jobId: string,
  response: Awaited<ReturnType<typeof pausePipeline>>,
) {
  const state = useAppStore.getState();
  if (state.currentJob?.id !== jobId) return;
  state.setPipeline(mapPipelineFromApi(response));
  state.setPipelineExecution(mapExecutionFromApi(response));
}

/** Pause the running pipeline; the current stage stops and can be resumed later. */
export async function pauseCurrentPipeline(): Promise<boolean> {
  const { currentJob, settings } = useAppStore.getState();
  if (!currentJob || !requireBackend("pause the pipeline")) return false;
  try {
    const response = await pausePipeline(currentJob.id, settings.backendUrl);
    await applyControlResponse(currentJob.id, response);
    toast.success("Pause requested", {
      description: "The current stage stops and will run again when you resume.",
    });
    return true;
  } catch (error) {
    toast.error("Could not pause", { description: errorMessage(error) });
    return false;
  }
}

/** Cancel the running pipeline; completed stages are kept. */
export async function cancelCurrentPipeline(): Promise<boolean> {
  const { currentJob, settings } = useAppStore.getState();
  if (!currentJob || !requireBackend("cancel the pipeline")) return false;
  try {
    const response = await cancelPipeline(currentJob.id, settings.backendUrl);
    await applyControlResponse(currentJob.id, response);
    toast.success("Cancellation requested", {
      description: "The running stage stops; completed stages are kept.",
    });
    return true;
  } catch (error) {
    toast.error("Could not cancel", { description: errorMessage(error) });
    return false;
  }
}

/** Select an existing job as the active workspace job. */
export async function openExistingJob(jobId: string): Promise<void> {
  const { settings, jobs } = useAppStore.getState();

  if (!requireBackend("open the job")) return;

  appendLine({ level: "info", msg: `Opening job ${jobId}...` });

  try {
    const job = await getJob(jobId, settings.backendUrl);
    if (!job) {
      appendLine({ level: "error", msg: `Job not found: ${jobId}` });
      return;
    }

    const known = jobs.some((entry) => entry.id === job.id);
    if (!known) {
      useAppStore.getState().setJobs([job, ...jobs]);
    } else {
      replaceJobInStore(job);
    }

    useAppStore.getState().setCurrentJob(job);
    useAppStore.getState().setViewer({ selectedJobId: job.id });
    const pipeline = await loadPipelineForJob(job);
    useAppStore.getState().setPipeline(pipeline);
    appendLine({ level: "ok", msg: `Active job: ${job.id}` });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    appendLine({ level: "error", msg: `Failed to open job: ${message}` });
  }
}

/** Upload images to the active job. */
export async function uploadImagesForCurrentJob(files: File[]): Promise<void> {
  const { settings, currentJob, setUpload } = useAppStore.getState();

  if (!requireBackend("upload images")) {
    setUpload({ status: "error", progress: 0, error: backendUnavailableReason() });
    return;
  }

  if (!currentJob) {
    setUpload({ status: "error", progress: 0, error: "No active job" });
    appendLine({ level: "error", msg: "Create a job before uploading images." });
    return;
  }

  const validation = validateUploadFiles(files);
  validation.warnings.forEach((warning) => {
    appendLine({ level: "warn", msg: warning });
  });
  if (validation.error || validation.accepted.length === 0) {
    const message = validation.error ?? "No supported images";
    setUpload({ status: "error", progress: 0, error: message });
    appendLine({ level: "error", msg: message });
    return;
  }

  const batches = chunkUploadFiles(validation.accepted);
  const totalBytes = validation.accepted.reduce((sum, file) => sum + file.size, 0);
  let uploadedBytes = 0;

  setUpload({ status: "uploading", progress: 0, error: null });
  appendLine({ level: "info", msg: `Receiving ${validation.accepted.length} image(s)...` });
  appendLine({ level: "info", msg: "Validating..." });

  try {
    appendLine({ level: "info", msg: "Saving..." });
    let lastResult: Awaited<ReturnType<typeof uploadImages>> | null = null;

    for (const batch of batches) {
      const batchBytes = batch.reduce((sum, file) => sum + file.size, 0);
      lastResult = await uploadImages(
        currentJob.id,
        batch,
        settings.backendUrl,
        (batchProgress) => {
          const loaded = uploadedBytes + (batchBytes * batchProgress) / 100;
          const overall = totalBytes > 0 ? Math.round((loaded / totalBytes) * 100) : batchProgress;
          setUpload({ status: "uploading", progress: overall, error: null });
        },
      );
      uploadedBytes += batchBytes;
      setUpload({
        status: "uploading",
        progress: totalBytes > 0 ? Math.round((uploadedBytes / totalBytes) * 100) : 100,
        error: null,
      });
    }

    appendLine({ level: "info", msg: "Generating previews..." });

    const refreshed = await getJob(currentJob.id, settings.backendUrl);
    if (refreshed) {
      replaceJobInStore(refreshed);
      await refreshCurrentJobPipeline(refreshed);
    }

    setUpload({ status: "success", progress: 100, error: null });
    appendLine({ level: "ok", msg: "Upload complete." });
    lastResult?.uploaded.forEach((name) => {
      appendLine({ level: "info", msg: `Saved: ${name}` });
    });
  } catch (error) {
    const message = errorMessage(error);
    setUpload({ status: "error", progress: 0, error: message });
    appendLine({ level: "error", msg: `Upload failed: ${message}` });
    toast.error("Upload failed", { description: message });
  }
}

/** Run the reconstruction pipeline for the active job. */
export async function startPipelineForCurrentJob(): Promise<void> {
  const { settings, currentJob, pipeline } = useAppStore.getState();

  if (!requireBackend("start the pipeline")) return;

  if (!currentJob) {
    appendLine({ level: "error", msg: "Create a job before starting the pipeline." });
    return;
  }

  if (!canStartPipeline(pipeline, currentJob.imageCount ?? 0)) {
    appendLine({ level: "error", msg: "Pipeline is not ready for this job." });
    return;
  }

  const nextStageId = findNextRunnableStage(pipeline)?.id ?? 2;
  const runningPipeline = pipeline.map((step) =>
    step.id === nextStageId ? { ...step, status: "running" as const, progress: 0 } : step,
  );
  useAppStore.getState().setPipeline(runningPipeline);

  // The request blocks until the run stops; live logs arrive via usePipelineActivity polling,
  // so result.logs is not appended here (it would duplicate the streamed lines).
  useAppStore.getState().setPipelineRequestActive(true);
  try {
    const result = await startPipeline(currentJob.id, settings.backendUrl);
    appendLine({
      level: "info",
      msg: `Pipeline request finished (${result.stopped_reason}).`,
      jobId: currentJob.id,
    });
    notifyRunFinished(result.stopped_reason);
    await refreshCurrentJobPipeline(currentJob);
    void refreshJobList();
  } catch (error) {
    const message = errorMessage(error);
    appendLine({ level: "error", msg: `Pipeline failed: ${message}`, jobId: currentJob.id });
    toast.error("Pipeline request failed", { description: message });
    await refreshCurrentJobPipeline(currentJob).catch(() => undefined);
  } finally {
    useAppStore.getState().setPipelineRequestActive(false);
  }
}

/** Load persisted jobs from GET /api/jobs. */
export async function syncJobsFromBackend(): Promise<void> {
  const { settings, backendHealth } = useAppStore.getState();
  if (backendHealth.status !== "connected") return;

  try {
    const jobs = await getJobs(settings.backendUrl);
    // The backend URL changed while this request was in flight: these jobs belong to the old
    // backend, and applying them would make the dashboard query them on the new one.
    if (useAppStore.getState().settings.backendUrl !== settings.backendUrl) return;
    const currentJob = useAppStore.getState().currentJob;
    const nextCurrent =
      currentJob && jobs.some((job) => job.id === currentJob.id)
        ? (jobs.find((job) => job.id === currentJob.id) ?? jobs[0] ?? null)
        : (jobs[0] ?? null);

    useAppStore.getState().setJobs(jobs);
    useAppStore.getState().setCurrentJob(nextCurrent);

    const pipeline = await loadPipelineForJob(nextCurrent);
    useAppStore.getState().setPipeline(pipeline);
  } catch {
    // Keep existing local state if sync fails
  }
}

/**
 * Refresh job records (status, progress, metrics) from GET /api/jobs without touching the
 * selected job or its pipeline view, so runs finished in another tab or via the API show up.
 */
export async function refreshJobList(): Promise<void> {
  const { settings, backendHealth } = useAppStore.getState();
  if (backendHealth.status !== "connected") return;
  try {
    const jobs = await getJobs(settings.backendUrl);
    const state = useAppStore.getState();
    if (state.settings.backendUrl !== settings.backendUrl) return;
    state.setJobs(jobs);
    const current = state.currentJob ? jobs.find((job) => job.id === state.currentJob?.id) : null;
    if (current) state.setCurrentJob(current);
  } catch {
    // Keep the existing list; the next refresh retries.
  }
}

/** Toast describing why a pipeline run request returned. */
export function notifyRunFinished(stoppedReason: string): void {
  const messages: Record<string, [boolean, string]> = {
    completed: [true, "Pipeline run finished"],
    paused: [true, "Pipeline paused"],
    cancelled: [true, "Pipeline cancelled"],
    stage_failed: [false, "Pipeline stopped: a stage failed"],
    stage_not_runnable: [false, "Pipeline could not continue: a stage is not runnable"],
    no_pending_stage: [true, "Nothing left to run"],
  };
  const [ok, text] = messages[stoppedReason] ?? [true, `Pipeline stopped (${stoppedReason})`];
  if (ok) toast.success(text);
  else toast.error(text, { description: "See the terminal for the stage log." });
}
