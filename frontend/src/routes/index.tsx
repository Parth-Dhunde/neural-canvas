import { createFileRoute, Link } from "@tanstack/react-router";
import { useCallback, useRef, useState } from "react";
import { Upload, FileImage, Play, MoreHorizontal, Boxes, BookOpen } from "lucide-react";
import { PageHeader, Panel, Metric, ButtonPro } from "@/components/ui-pro/Panel";
import { Pipeline } from "@/components/pipeline/Pipeline";
import { StatusBadge } from "@/components/ui-pro/StatusBadge";
import { ProgressBar } from "@/components/ui-pro/ProgressBar";
import { HardwarePanel } from "@/components/ui-pro/HardwarePanel";
import { EmptyState } from "@/components/ui-pro/EmptyState";
import { APP_SUBTITLE } from "@/lib/constants";
import { collectFilesFromDataTransfer } from "@/lib/collectUploadFiles";
import { openFilePicker } from "@/lib/openFilePicker";
import {
  createNewJob,
  openExistingJob,
  runBackgroundRemovalForCurrentJob,
  uploadImagesForCurrentJob,
} from "@/lib/jobActions";
import { useHardwareTelemetry } from "@/hooks/useHardwareTelemetry";
import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import {
  formatBytes,
  formatDuration,
  formatMedianStatistic,
  formatMib,
  NOT_RECORDED,
  pipelineSnapshotMetrics,
} from "@/lib/dashboardStats";
import { canStartPipeline } from "@/lib/pipeline";
import { getJobPreviewUrls } from "@/services/jobs";
import { getJob } from "@/services/jobs";
import { getPipeline, startPipeline } from "@/services/pipeline";
import { useAppStore } from "@/store/useAppStore";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

export const Route = createFileRoute("/")({
  component: Dashboard,
  head: () => ({
    meta: [
      { title: "Dashboard — NeuralCanvas" },
      {
        name: "description",
        content: `${APP_SUBTITLE}. Ingest images, monitor training pipelines, and inspect hardware.`,
      },
    ],
  }),
});

function Dashboard() {
  useHardwareTelemetry(true);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [dropBusy, setDropBusy] = useState(false);
  const [starting, setStarting] = useState(false);
  const jobs = useAppStore((s) => s.jobs);
  const currentJob = useAppStore((s) => s.currentJob);
  const selectedEngine = useAppStore((s) => s.selectedEngine);
  const pipeline = useAppStore((s) => s.pipeline);
  const upload = useAppStore((s) => s.upload);
  const settings = useAppStore((s) => s.settings);
  const setJobs = useAppStore((s) => s.setJobs);
  const setCurrentJob = useAppStore((s) => s.setCurrentJob);
  const setPipeline = useAppStore((s) => s.setPipeline);
  const setViewer = useAppStore((s) => s.setViewer);
  const appendTerminalLine = useAppStore((s) => s.appendTerminalLine);
  const recentJobs = jobs.slice(0, 6);
  const { summary, error: summaryError } = useDashboardSummary();
  const engineStats = summary?.engines[selectedEngine] ?? null;
  const experimental = summary?.experimental ?? [];
  const snapshotMetrics = pipelineSnapshotMetrics(currentJob);
  const summaryHint = summaryError ? "Statistics unavailable" : "Loading…";

  const imageCount = currentJob?.imageCount ?? 0;
  const previewUrls =
    currentJob && imageCount > 0 ? getJobPreviewUrls(currentJob, settings.backendUrl) : [];

  const uploadStageOneDone = pipeline[0]?.status === "completed";
  const pipelineReady = canStartPipeline(pipeline, imageCount);
  const pipelineRunning = pipeline.some((step) => step.status === "running");
  const pipelineComplete =
    pipeline.length > 0 && pipeline.every((step) => step.status === "completed");
  const failedStep = pipeline.find((step) => step.status === "failed");

  function terminalTime(): string {
    const d = new Date();
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
  }

  function logTerminal(level: "info" | "warn" | "error" | "ok", msg: string, jobId?: string) {
    appendTerminalLine({ time: terminalTime(), level, msg, jobId });
  }

  async function handleStartReconstruction() {
    const debug = import.meta.env.DEV;
    if (debug) console.log("Start Reconstruction clicked");

    if (!currentJob) {
      logTerminal("error", "Create a job before starting reconstruction.");
      toast.error("No active job");
      return;
    }

    if (debug) console.log("Job ID", currentJob.id);

    if ((currentJob.imageCount ?? 0) <= 0) {
      logTerminal("error", "Upload at least one image before starting reconstruction.");
      toast.error("No images uploaded");
      return;
    }

    if (!canStartPipeline(pipeline, currentJob.imageCount ?? 0)) {
      logTerminal("error", "Pipeline is not ready for this job.");
      toast.error("Pipeline not ready");
      return;
    }

    setStarting(true);
    useAppStore.getState().setPipelineRequestActive(true);
    try {
      const baseUrl = settings.backendUrl;
      if (debug) console.log("POST /pipeline/start");

      // Mark viewer as loading so it can auto-refresh once mesh becomes available.
      setViewer({ displayState: "loading" });

      const result = await startPipeline(currentJob.id, baseUrl);
      if (debug) {
        console.log("HTTP status", "ok");
        console.log("Response JSON", result);
      }

      // Live logs are streamed by usePipelineActivity; appending result.logs would duplicate them.
      logTerminal("info", `Pipeline request finished (${result.stopped_reason}).`, currentJob.id);

      // Reload job + pipeline state after pipeline execution.
      // Read the job list from the store now: the `jobs` captured when this (possibly long)
      // run started would overwrite updates made meanwhile with stale values.
      const refreshed = await getJob(currentJob.id, baseUrl);
      if (refreshed) {
        const latest = useAppStore.getState().jobs;
        setJobs(latest.map((j) => (j.id === refreshed.id ? refreshed : j)));
        setCurrentJob(refreshed);
      }

      const nextPipeline = await getPipeline(currentJob.id, baseUrl);
      setPipeline(nextPipeline);

      if (result.stopped_reason === "stage_failed") {
        toast.error("Pipeline stopped: a stage failed");
      } else {
        toast.success("Pipeline run finished");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      logTerminal("error", `Pipeline failed: ${message}`, currentJob.id);
      toast.error(message);
    } finally {
      useAppStore.getState().setPipelineRequestActive(false);
      setStarting(false);
    }
  }

  const handleFiles = useCallback((files: FileList | File[]) => {
    const list = Array.from(files);
    if (list.length > 0) void uploadImagesForCurrentJob(list);
  }, []);

  const onDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    setDropBusy(true);
    try {
      const collected = await collectFilesFromDataTransfer(e.dataTransfer);
      if (collected.length > 0) {
        await uploadImagesForCurrentJob(collected);
      } else {
        toast.error("No supported images found in drop");
      }
    } catch {
      toast.error("Could not read dropped files");
    } finally {
      setDropBusy(false);
    }
  }, []);

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        description="Ingest source imagery, launch reconstructions, and monitor the active pipeline."
        actions={
          <>
            <Link
              to="/guide"
              className="inline-flex h-8 items-center gap-1.5 rounded-sm px-3 text-[12px] font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:bg-surface-2 hover:text-ivory"
            >
              <BookOpen className="h-3.5 w-3.5" strokeWidth={1.7} /> How to use
            </Link>
            <ButtonPro variant="outline" reason="Presets are not implemented yet">
              Import Preset
            </ButtonPro>
            <ButtonPro
              variant="warm"
              onClick={() => void handleStartReconstruction()}
              loading={starting}
              disabled={
                !currentJob || upload.status === "uploading" || pipelineRunning || pipelineComplete
              }
              title={pipelineComplete ? "Every stage of this job has completed" : undefined}
            >
              {starting ? (
                "Running…"
              ) : (
                <>
                  <Play className="h-3 w-3" /> Start Reconstruction
                </>
              )}
            </ButtonPro>
          </>
        }
      />

      <div className="grid grid-cols-12 gap-4 p-4 sm:p-6">
        <Panel
          title="Ingest · Multi-view Imagery"
          className="col-span-12 xl:col-span-8"
          action={
            <div className="flex items-center gap-2">
              <span className="mono text-[11px] text-subtle">
                {imageCount > 0
                  ? `${imageCount} images · ${currentJob?.id ?? ""}`
                  : currentJob
                    ? "No images uploaded"
                    : "No active job"}
              </span>
              {upload.status === "uploading" && (
                <span className="mono text-[11px] text-bronze">Uploading {upload.progress}%</span>
              )}
              {upload.status === "success" && (
                <span className="mono text-[11px] text-success">Uploaded</span>
              )}
              {upload.status === "error" && (
                <span className="mono text-[11px] text-destructive">Failed</span>
              )}
            </div>
          }
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length) handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <input
            ref={folderInputRef}
            type="file"
            accept="image/jpeg,image/png"
            multiple
            className="hidden"
            {...({
              webkitdirectory: "",
              directory: "",
            } as React.InputHTMLAttributes<HTMLInputElement>)}
            onChange={(e) => {
              if (e.target.files?.length) handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            className={cn(
              "relative flex flex-col items-center justify-center rounded-sm border border-dashed p-8 transition-colors",
              drag
                ? "border-selected bg-selected/6"
                : "border-border-strong bg-surface-2/60 hover:bg-surface-2",
            )}
          >
            <div className="grid h-12 w-12 place-items-center rounded-sm border border-border-strong bg-surface-3">
              <Upload className="h-5 w-5 text-bronze" strokeWidth={1.6} />
            </div>
            <div className="mt-3 mono text-[13px] text-ivory">Drop images or a folder to begin</div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              Supports JPG · JPEG · PNG &nbsp;·&nbsp; 24 to 500 views recommended
            </div>
            {!currentJob && (
              <div className="mt-2 text-[11px] text-warning">
                Create a job before uploading images.
              </div>
            )}
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              <ButtonPro
                variant="bronze"
                size="sm"
                disabled={!currentJob || upload.status === "uploading" || dropBusy}
                onClick={() => {
                  if (!openFilePicker(fileInputRef.current)) {
                    toast.error("Could not open file chooser");
                  }
                }}
              >
                <FileImage className="h-3 w-3" /> Browse files
              </ButtonPro>
              <ButtonPro
                variant="outline"
                size="sm"
                disabled={!currentJob || upload.status === "uploading" || dropBusy}
                onClick={() => {
                  if (!openFilePicker(folderInputRef.current)) {
                    toast.error("Could not open folder chooser");
                  }
                }}
              >
                Browse folder
              </ButtonPro>
              <ButtonPro variant="outline" size="sm" onClick={() => void createNewJob()}>
                Create New Job
              </ButtonPro>
              {jobs.length > 0 && (
                <select
                  className="mono h-8 rounded-sm border border-border bg-surface-2 px-2 text-[11px] text-ivory"
                  defaultValue=""
                  onChange={(e) => {
                    const jobId = e.target.value;
                    e.target.value = "";
                    if (jobId) void openExistingJob(jobId);
                  }}
                >
                  <option value="" disabled>
                    Continue existing job
                  </option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.id} · {job.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
            {dropBusy && (
              <div className="mt-2 text-[11px] text-muted-foreground">Reading dropped files…</div>
            )}
          </div>

          {upload.status === "uploading" && (
            <div className="mt-4">
              <ProgressBar value={upload.progress} tone="bronze" />
            </div>
          )}

          {upload.status === "error" && upload.error && (
            <div className="mt-3 mono text-[11px] text-destructive">{upload.error}</div>
          )}

          {previewUrls.length > 0 && (
            <div className="mt-4 grid grid-cols-4 gap-2 md:grid-cols-8">
              {previewUrls.slice(0, 16).map((url, i) => (
                <motion.div
                  key={`${url}-${i}`}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.02, 0.2) }}
                  className="group relative aspect-square overflow-hidden rounded-sm border border-border bg-surface-3"
                >
                  <img
                    src={url}
                    alt={currentJob?.imageFilenames?.[i] ?? `Image ${i + 1}`}
                    className="h-full w-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-background/90 to-transparent p-1">
                    <div className="mono truncate text-[9px] text-ivory">
                      {currentJob?.imageFilenames?.[i] ?? `Image ${i + 1}`}
                    </div>
                  </div>
                  <div className="absolute left-1 top-1 mono rounded-sm bg-background/70 px-1 text-[9px] text-bronze">
                    {String(i + 1).padStart(3, "0")}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Hardware · Runtime" className="col-span-12 xl:col-span-4">
          <HardwarePanel />
        </Panel>

        <Panel
          title={`Pipeline · ${currentJob ? currentJob.id : "No Job"}`}
          className="col-span-12"
          bodyClassName="p-3"
          action={
            <div className="flex items-center gap-3">
              <div className="mono flex items-center gap-1.5 text-[11px] text-subtle" role="status">
                {!currentJob
                  ? "No active job"
                  : pipelineComplete
                    ? "All stages complete · exports ready"
                    : failedStep && !pipelineRunning
                      ? `Stage ${failedStep.id} (${failedStep.name}) failed · retry available`
                      : pipelineRunning
                        ? pipeline[3]?.status === "running"
                          ? "Reconstruction running"
                          : pipeline[2]?.status === "running"
                            ? "Camera estimation running"
                            : "Pipeline running"
                        : uploadStageOneDone
                          ? pipelineReady
                            ? pipeline[1]?.status === "completed"
                              ? "Background removal complete · Ready"
                              : "Upload complete · Ready"
                            : pipeline[2]?.status === "completed"
                              ? "Camera estimation complete"
                              : pipeline[1]?.status === "completed"
                                ? "Background removal complete · Waiting"
                                : "Upload complete · Waiting"
                          : "Waiting"}
              </div>
              <ButtonPro
                size="sm"
                variant="bronze"
                disabled={!pipelineReady || pipelineRunning || pipelineComplete}
                onClick={() => void runBackgroundRemovalForCurrentJob()}
                title="Runs every remaining stage in order"
              >
                {pipelineComplete
                  ? "Pipeline complete"
                  : failedStep
                    ? `Retry from stage ${failedStep.id}`
                    : "Run remaining stages"}
              </ButtonPro>
              <ButtonPro
                size="sm"
                variant="ghost"
                reason="Pause exists in the API but is not wired up in the dashboard yet"
              >
                Pause
              </ButtonPro>
              <ButtonPro
                size="sm"
                variant="ghost"
                reason="Cancel exists in the API but is not wired up in the dashboard yet"
              >
                Cancel
              </ButtonPro>
            </div>
          }
        >
          <Pipeline />
        </Panel>

        <div className="col-span-12 grid grid-cols-2 gap-4 lg:col-span-4 lg:grid-cols-2">
          <Metric
            label="Active Jobs"
            value={summary ? String(summary.jobs.active) : "—"}
            hint={summary ? `Queued or running · ${summary.jobs.total} total` : summaryHint}
          />
          <Metric
            label="Completed · 7d"
            value={summary ? String(summary.jobs.completed_7d) : "—"}
            hint={summary ? `${summary.jobs.completed_total} completed all time` : summaryHint}
          />
          {(() => {
            const training = formatMedianStatistic(summary?.training, formatDuration);
            return (
              <Metric
                label="Median Training"
                value={training.value}
                hint={summary ? training.hint : summaryHint}
              />
            );
          })()}
          <Metric
            label="Storage"
            value={summary ? formatBytes(summary.storage.bytes) : "—"}
            hint={summary ? "Job workspaces (jobs/)" : summaryHint}
          />
        </div>

        <Panel
          title="Recent Jobs"
          className="col-span-12 lg:col-span-8"
          action={
            <Link to="/jobs">
              <ButtonPro size="sm" variant="ghost">
                View all →
              </ButtonPro>
            </Link>
          }
          bodyClassName="p-0"
        >
          {recentJobs.length === 0 ? (
            <EmptyState
              title="No reconstruction jobs yet."
              action={
                <ButtonPro variant="bronze" onClick={() => void createNewJob()}>
                  Create New Job
                </ButtonPro>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <div className="min-w-[720px]">
                <div className="hairline-b grid grid-cols-[80px_1fr_140px_120px_1fr_80px_28px] gap-3 bg-surface/60 px-4 py-2 text-[10px] uppercase tracking-widest text-subtle">
                  <span>ID</span>
                  <span>Name</span>
                  <span>Engine</span>
                  <span>Status</span>
                  <span>Progress</span>
                  <span title="Stage 4 (Instant-NGP) training wall-clock time">Training</span>
                  <span />
                </div>
                {recentJobs.map((j) => (
                  <div
                    key={j.id}
                    role="button"
                    tabIndex={0}
                    title={
                      j.status === "failed" && j.lastError
                        ? `Stage ${j.failedStage?.id ?? "?"} (${j.failedStage?.name ?? "unknown"}) failed: ${j.lastError}`
                        : undefined
                    }
                    onClick={() => void openExistingJob(j.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        void openExistingJob(j.id);
                      }
                    }}
                    className="hairline-b grid cursor-pointer grid-cols-[80px_1fr_140px_120px_1fr_80px_28px] items-center gap-3 px-4 py-2.5 text-[12px] hover:bg-surface-2/60"
                  >
                    <span className="mono text-bronze">{j.id}</span>
                    <span className="truncate text-ivory">{j.name}</span>
                    <span className="mono text-muted-foreground">{j.engine}</span>
                    <StatusBadge status={j.status} />
                    <div className="flex items-center gap-2">
                      <ProgressBar
                        value={j.progress}
                        tone={
                          j.status === "failed"
                            ? "destructive"
                            : j.status === "completed"
                              ? "success"
                              : "bronze"
                        }
                        className="w-full"
                      />
                      <span className="mono w-10 text-right text-[10px] text-subtle">
                        {j.progress}%
                      </span>
                    </div>
                    <span className="mono text-muted-foreground">{j.duration ?? "—"}</span>
                    <button
                      aria-label={`Open ${j.id}`}
                      className="grid h-6 w-6 place-items-center rounded-sm text-subtle hover:bg-surface-3 hover:text-ivory"
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel title="Current Engine" className="col-span-12 lg:col-span-6">
          <div className="flex items-start gap-4">
            <div className="hidden h-14 w-14 shrink-0 place-items-center sm:grid rounded-sm border border-bronze/40 bg-bronze/10">
              <Boxes className="h-6 w-6 text-bronze" strokeWidth={1.4} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="label-caps">Neural Reconstruction</div>
              <div className="mono mt-1 text-[16px] text-ivory">{selectedEngine}</div>
              <p className="mt-1 text-[12px] text-muted-foreground">
                {engineStats
                  ? `Medians over ${engineStats.completed_jobs} completed ${selectedEngine} job${engineStats.completed_jobs === 1 ? "" : "s"}; jobs without a measurement are excluded.`
                  : summaryHint}
              </p>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <MiniStat
                  label="Median PSNR"
                  {...formatMedianStatistic(
                    engineStats?.median_psnr_db,
                    (v) => `${v.toFixed(2)} dB`,
                    "evaluated",
                    "Not evaluated",
                  )}
                />
                <MiniStat
                  label="Median time"
                  {...formatMedianStatistic(
                    engineStats?.median_training_seconds,
                    formatDuration,
                    "completed",
                    NOT_RECORDED,
                  )}
                />
                <MiniStat
                  label="Median VRAM"
                  {...formatMedianStatistic(
                    engineStats?.median_peak_vram_mib,
                    formatMib,
                    "completed",
                    NOT_RECORDED,
                  )}
                />
              </div>
              {experimental.length > 0 && (
                <div className="mt-3 rounded-sm border border-dashed border-border-strong p-2.5">
                  <div className="label-caps text-warning">Experimental · not production</div>
                  <ul className="mt-1.5 space-y-1">
                    {experimental.map((e) => (
                      <li
                        key={e.record}
                        className="mono text-[11px] text-muted-foreground"
                        title={e.record}
                      >
                        {e.experiment}:{" "}
                        {e.psnr_mean_db !== null ? `${e.psnr_mean_db.toFixed(2)} dB` : "PSNR N/A"}
                        {e.baseline_psnr_mean_db !== null &&
                          ` (production baseline ${e.baseline_psnr_mean_db.toFixed(2)} dB)`}
                        {e.frames_evaluated !== null && ` · ${e.frames_evaluated} frames`}
                        {e.peak_vram_mib !== null && ` · peak ${e.peak_vram_mib} MiB`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </Panel>

        <Panel
          title={`Pipeline Snapshot · ${currentJob ? currentJob.id : "No Job"}`}
          className="col-span-12 lg:col-span-6"
        >
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
            {snapshotMetrics.map((m) => (
              <div
                key={m.label}
                title={m.hint}
                className="nc-tile rounded-sm border border-border p-3"
              >
                <div className="label-caps">{m.label}</div>
                <div
                  className={cn(
                    "mono mt-1 text-[18px]",
                    m.available ? "text-ivory" : "text-subtle",
                  )}
                >
                  {m.value}
                </div>
                <div className="mt-0.5 text-[11px] text-subtle">{m.hint}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function MiniStat({
  label,
  value,
  hint,
  available,
}: {
  label: string;
  value: string;
  hint: string;
  available: boolean;
}) {
  return (
    <div className="nc-tile rounded-sm border border-border p-2 text-center" title={hint}>
      <div className="label-caps">{label}</div>
      <div className={cn("mono mt-1 text-[13px]", available ? "text-ivory" : "text-subtle")}>
        {value}
      </div>
      <div className="mt-0.5 truncate text-[10px] text-subtle">{hint}</div>
    </div>
  );
}
