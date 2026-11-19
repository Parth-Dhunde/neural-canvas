import { canStartPipeline, findNextRunnableStage, pipelineForJob } from "@/lib/pipeline";
import { chunkUploadFiles, validateUploadFiles } from "@/lib/uploadLimits";
import { createJob, getJob, getJobs, uploadImages } from "@/services/jobs";
import { getPipeline, startPipeline } from "@/services/pipeline";
import { useAppStore } from "@/store/useAppStore";
import type { Job, LogEntry, PipelineStep } from "@/types";

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
export async function createNewJob(): Promise<void> {
  const { settings, backendHealth } = useAppStore.getState();

  if (backendHealth.status !== "connected") {
    appendLine({ level: "error", msg: "Cannot create job — backend disconnected." });
    return;
  }

  appendLine({ level: "info", msg: "Creating job..." });

  try {
    const job = await createJob({ engine: "Instant-NGP" }, settings.backendUrl);
    useAppStore.getState().addJob(job);
    const pipeline = await loadPipelineForJob(job);
    useAppStore.getState().setPipeline(pipeline);
    appendLine({ level: "ok", msg: "Job created." });
    appendLine({ level: "info", msg: `Job ID: ${job.id}` });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    appendLine({ level: "error", msg: `Failed to create job: ${message}` });
  }
}

/** Select an existing job as the active workspace job. */
export async function openExistingJob(jobId: string): Promise<void> {
  const { settings, backendHealth, jobs } = useAppStore.getState();

  if (backendHealth.status !== "connected") {
    appendLine({ level: "error", msg: "Cannot open job — backend disconnected." });
    return;
  }

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
  const { settings, backendHealth, currentJob, setUpload } = useAppStore.getState();

  if (backendHealth.status !== "connected") {
    setUpload({ status: "error", progress: 0, error: "Backend disconnected" });
    appendLine({ level: "error", msg: "Cannot upload — backend disconnected." });
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
    const message = error instanceof Error ? error.message : "Unknown error";
    setUpload({ status: "error", progress: 0, error: message });
    appendLine({ level: "error", msg: `Upload failed: ${message}` });
  }
}

/** Run the reconstruction pipeline for the active job. */
export async function startPipelineForCurrentJob(): Promise<void> {
  const { settings, backendHealth, currentJob, pipeline } = useAppStore.getState();

  if (backendHealth.status !== "connected") {
    appendLine({ level: "error", msg: "Cannot start pipeline — backend disconnected." });
    return;
  }

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
    await refreshCurrentJobPipeline(currentJob);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    appendLine({ level: "error", msg: `Pipeline failed: ${message}`, jobId: currentJob.id });
    await refreshCurrentJobPipeline(currentJob);
  } finally {
    useAppStore.getState().setPipelineRequestActive(false);
  }
}

/** @deprecated Use startPipelineForCurrentJob — kept as alias for existing UI hooks. */
export async function runBackgroundRemovalForCurrentJob(): Promise<void> {
  return startPipelineForCurrentJob();
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
