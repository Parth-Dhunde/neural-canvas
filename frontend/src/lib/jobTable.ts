// Jobs table logic: filtering, sorting, paging, CSV export and applying deletions.
// Runtime-import free so it can be unit-tested with `node --test`.
import type { Job, JobStatus } from "@/types";

export type JobSortKey = "id" | "createdAt" | "duration" | "progress";
export type SortDirection = "asc" | "desc";
export type OutputsFilter = "any" | "mesh" | "exports" | "none";
export type CreatedFilter = "any" | "24h" | "7d" | "30d";

export interface JobFilters {
  status: JobStatus | "all";
  engine: string; // "all" or an engine id
  query: string;
  outputs: OutputsFilter;
  created: CreatedFilter;
}

export const DEFAULT_JOB_FILTERS: JobFilters = {
  status: "all",
  engine: "all",
  query: "",
  outputs: "any",
  created: "any",
};

const CREATED_WINDOW_MS: Record<Exclude<CreatedFilter, "any">, number> = {
  "24h": 24 * 3600 * 1000,
  "7d": 7 * 24 * 3600 * 1000,
  "30d": 30 * 24 * 3600 * 1000,
};

function hasExports(job: Job): boolean {
  return Object.values(job.jobOutputs?.exports ?? {}).some((formats) => formats.length > 0);
}

/** Number of "More filters" options that differ from their defaults. */
export function activeExtraFilterCount(filters: JobFilters): number {
  return (filters.outputs !== "any" ? 1 : 0) + (filters.created !== "any" ? 1 : 0);
}

export function filterJobs(jobs: Job[], filters: JobFilters, now = Date.now()): Job[] {
  const query = filters.query.trim().toLowerCase();
  return jobs.filter((job) => {
    if (filters.status !== "all" && job.status !== filters.status) return false;
    if (filters.engine !== "all" && job.engine !== filters.engine) return false;
    if (query && !`${job.id} ${job.name}`.toLowerCase().includes(query)) return false;
    if (filters.outputs === "mesh" && !job.jobOutputs?.mesh) return false;
    if (filters.outputs === "exports" && !hasExports(job)) return false;
    if (filters.outputs === "none" && (job.jobOutputs?.mesh || hasExports(job))) return false;
    if (filters.created !== "any") {
      const created = Date.parse(job.createdAt);
      if (Number.isNaN(created) || now - created > CREATED_WINDOW_MS[filters.created]) return false;
    }
    return true;
  });
}

export function sortJobs(jobs: Job[], key: JobSortKey, direction: SortDirection): Job[] {
  const sign = direction === "asc" ? 1 : -1;
  const value = (job: Job): number | string => {
    if (key === "progress") return job.progress;
    if (key === "duration") return job.trainingDurationSeconds ?? -1;
    if (key === "id") return job.id;
    return Date.parse(job.createdAt) || 0;
  };
  return [...jobs].sort((a, b) => {
    const va = value(a);
    const vb = value(b);
    const order =
      typeof va === "number" && typeof vb === "number"
        ? va - vb
        : String(va).localeCompare(String(vb));
    return order === 0 ? a.id.localeCompare(b.id) * sign : order * sign;
  });
}

export interface Page<T> {
  items: T[];
  page: number; // 1-based, clamped to the available pages
  pageCount: number;
  start: number; // 1-based index of the first item, 0 when empty
  end: number;
}

export function paginate<T>(items: T[], page: number, pageSize: number): Page<T> {
  const size = Math.max(1, Math.floor(pageSize));
  const pageCount = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(1, Math.floor(page) || 1), pageCount);
  const offset = (current - 1) * size;
  const slice = items.slice(offset, offset + size);
  return {
    items: slice,
    page: current,
    pageCount,
    start: slice.length ? offset + 1 : 0,
    end: offset + slice.length,
  };
}

const CSV_COLUMNS: [string, (job: Job) => string | number | null | undefined][] = [
  ["id", (j) => j.id],
  ["name", (j) => j.name],
  ["status", (j) => j.status],
  ["engine", (j) => j.engine],
  ["progress_percent", (j) => j.progress],
  ["images", (j) => j.imageCount ?? 0],
  ["created_at", (j) => j.createdAt],
  ["completed_at", (j) => j.completedAt ?? ""],
  ["training_seconds", (j) => j.trainingDurationSeconds ?? ""],
  ["final_loss", (j) => j.trainingMetrics?.finalLoss ?? ""],
  ["failed_stage", (j) => (j.failedStage ? `${j.failedStage.id} ${j.failedStage.name}` : "")],
  ["last_error", (j) => j.lastError ?? ""],
  [
    "exports",
    (j) =>
      Object.entries(j.jobOutputs?.exports ?? {})
        .map(([variant, formats]) => `${variant}:${formats.join("/")}`)
        .join(" "),
  ],
];

function csvCell(value: string | number | null | undefined): string {
  let text = value === null || value === undefined ? "" : String(value);
  // Spreadsheet formula injection: neutralise cells that would be evaluated.
  if (/^[=+\-@\t\r]/.test(text) && typeof value === "string") text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function jobsToCsv(jobs: Job[]): string {
  const header = CSV_COLUMNS.map(([name]) => name).join(",");
  const rows = jobs.map((job) => CSV_COLUMNS.map(([, get]) => csvCell(get(job))).join(","));
  return [header, ...rows].join("\r\n") + "\r\n";
}

/** Jobs that may be deleted now, and those refused because a run is in progress. */
export function splitDeletable(jobs: Job[], ids: Iterable<string>) {
  const wanted = new Set(ids);
  const selected = jobs.filter((job) => wanted.has(job.id));
  return {
    deletable: selected.filter((job) => job.status !== "running").map((job) => job.id),
    running: selected.filter((job) => job.status === "running").map((job) => job.id),
  };
}

export interface DeletionView {
  jobs: Job[];
  currentJob: Job | null;
  viewerJobId: string | null;
}

/** Remove deleted jobs everywhere the UI keeps them. */
export function applyDeletedJobs(view: DeletionView, deletedIds: Iterable<string>): DeletionView {
  const deleted = new Set(deletedIds);
  const jobs = view.jobs.filter((job) => !deleted.has(job.id));
  const currentJob =
    view.currentJob && deleted.has(view.currentJob.id) ? (jobs[0] ?? null) : view.currentJob;
  const viewerJobId = view.viewerJobId && deleted.has(view.viewerJobId) ? null : view.viewerJobId;
  return { jobs, currentJob, viewerJobId };
}
