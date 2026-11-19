// Pure helpers that turn backend job records and dashboard statistics into display values.
// Runtime-import free so they can be unit-tested with `node --test`. Missing measurements
// render as "N/A" with a reason; nothing here substitutes a default number.
import type { MedianStatisticApi } from "@/services/dashboard";
import type { Job, JobStatus } from "@/types";

export const UNAVAILABLE = "N/A";

/** Statuses the backend counts as active (mirrors app/jobs/lifecycle.py ACTIVE_STATUSES). */
export const ACTIVE_JOB_STATUSES: readonly JobStatus[] = ["queued", "running"];

export function isActiveJob(status: JobStatus): boolean {
  return ACTIVE_JOB_STATUSES.includes(status);
}

export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  if (m > 0) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return UNAVAILABLE;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 100 || unit === 0 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

export function formatLoss(loss: number): string {
  return loss >= 0.01 ? loss.toFixed(4) : loss.toExponential(2);
}

export interface DisplayMetric {
  label: string;
  value: string;
  hint: string;
  available: boolean;
}

function metric(
  label: string,
  value: string | null,
  hint: string,
  missing: { value: string; hint: string },
): DisplayMetric {
  return value === null
    ? { label, value: missing.value, hint: missing.hint, available: false }
    : { label, value, hint, available: true };
}

/** Label for a measurement that older runs never captured (distinct from a real zero). */
export const NOT_RECORDED = "Not recorded";

export const SNAPSHOT_LABELS = [
  "Loss (train)",
  "Throughput",
  "Checkpoints",
  "Peak VRAM",
  "Training time",
  "Pipeline time",
] as const;

/** Pipeline Snapshot values for the selected job, from its persisted training record. */
export function pipelineSnapshotMetrics(job: Job | null): DisplayMetric[] {
  if (!job) {
    return SNAPSHOT_LABELS.map((label) => ({
      label,
      value: "—",
      hint: "No active job",
      available: false,
    }));
  }

  const metrics = job.trainingMetrics ?? null;
  const pending = {
    value: UNAVAILABLE,
    hint:
      job.status === "running" ? "Available when training finishes" : "Training has not completed",
  };
  const fromLog = metrics?.source === "training_log";
  const step =
    metrics?.lastLoggedStep != null && metrics.totalSteps != null
      ? ` · step ${metrics.lastLoggedStep.toLocaleString("en-US")}/${metrics.totalSteps.toLocaleString("en-US")}`
      : "";
  const missingFromRun = (what: string) =>
    metrics ? { value: NOT_RECORDED, hint: `${what} was not recorded for this run` } : pending;

  const pipelineTime =
    job.pipelineDurationSeconds != null ? formatDuration(job.pipelineDurationSeconds) : null;
  const pipelineMissing =
    job.status === "completed"
      ? { value: NOT_RECORDED, hint: "Stage timings are recorded for runs from this version on" }
      : { value: UNAVAILABLE, hint: "Available when every stage has completed" };

  return [
    metric(
      SNAPSHOT_LABELS[0],
      metrics?.finalLoss != null ? formatLoss(metrics.finalLoss) : null,
      `Final logged loss${step}`,
      missingFromRun("Loss"),
    ),
    metric(
      SNAPSHOT_LABELS[1],
      metrics?.meanStepsPerSecond != null
        ? `${metrics.meanStepsPerSecond.toFixed(1)} steps/s`
        : null,
      `Mean training steps/s${fromLog ? " · read from training.log" : ""} (Instant-NGP does not log rays/s)`,
      missingFromRun("Step rate"),
    ),
    metric(
      SNAPSHOT_LABELS[2],
      metrics?.checkpointCount != null ? String(metrics.checkpointCount) : null,
      "Saved snapshots (.msgpack)",
      missingFromRun("Checkpoint count"),
    ),
    metric(
      SNAPSHOT_LABELS[3],
      metrics?.peakVramMib != null ? formatMib(metrics.peakVramMib) : null,
      "Peak GPU memory of the training process (nvidia-smi)",
      metrics
        ? {
            value: NOT_RECORDED,
            hint: fromLog
              ? "This run predates VRAM recording; its log has no GPU memory data"
              : "nvidia-smi reported no memory for the training process",
          }
        : pending,
    ),
    metric(
      SNAPSHOT_LABELS[4],
      job.trainingDurationSeconds != null ? formatDuration(job.trainingDurationSeconds) : null,
      "Stage 4 wall-clock time",
      pending,
    ),
    metric(SNAPSHOT_LABELS[5], pipelineTime, "Sum of measured stage run times", pipelineMissing),
  ];
}

export function formatMib(mib: number): string {
  return mib >= 1024 ? `${(mib / 1024).toFixed(2)} GB` : `${Math.round(mib)} MiB`;
}

const SAMPLE_NOUN = { evaluated: "evaluated job", completed: "completed job" } as const;

/** "36.73 dB" with "1 evaluated job", or `emptyLabel` with the backend's reason. */
export function formatMedianStatistic(
  stat: MedianStatisticApi | null | undefined,
  format: (value: number) => string,
  noun: keyof typeof SAMPLE_NOUN = "completed",
  /** Shown when there is no valid measurement, e.g. "Not evaluated" or "Not recorded". */
  emptyLabel: string = UNAVAILABLE,
): { value: string; hint: string; available: boolean } {
  if (!stat) return { value: "—", hint: "Loading statistics", available: false };
  if (stat.value === null || stat.sample_size === 0) {
    return {
      value: emptyLabel,
      hint: stat.unavailable_reason ?? "No valid measurements",
      available: false,
    };
  }
  const plural = stat.sample_size === 1 ? "" : "s";
  return {
    value: format(stat.value),
    hint: `Median · ${stat.sample_size} ${SAMPLE_NOUN[noun]}${plural}`,
    available: true,
  };
}

/** Change signature of the job list; the dashboard refetches statistics when it changes. */
export function jobsSignature(jobs: Job[]): string {
  return jobs.map((job) => `${job.id}:${job.status}:${job.progress}`).join("|");
}
