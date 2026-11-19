import { apiFetch } from "./api";
import type { LogEntry, LogLevel } from "@/types";

export interface JobLogEntryApi {
  seq: number;
  time: string;
  level: string;
  message: string;
  stage_id: number | null;
}

export interface JobLogsApiResponse {
  job_id: string;
  entries: JobLogEntryApi[];
  next_after: number;
  last_seq: number;
  has_more: boolean;
  truncated: boolean;
  reset: boolean;
}

/** GET /api/jobs/{id}/logs — pass `after` for incremental polls or `tail` for the latest N. */
export async function getJobLogs(
  jobId: string,
  query: { after?: number; limit?: number; tail?: number },
  baseUrl?: string,
): Promise<JobLogsApiResponse> {
  const params = new URLSearchParams();
  if (query.tail !== undefined) params.set("tail", String(query.tail));
  if (query.after !== undefined) params.set("after", String(query.after));
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  return apiFetch<JobLogsApiResponse>(
    `/api/jobs/${encodeURIComponent(jobId)}/logs?${params.toString()}`,
    { baseUrl },
  );
}

function toLevel(level: string): LogLevel {
  if (level === "warn" || level === "error" || level === "ok") return level;
  return "info";
}

function localTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

export function mapJobLogEntry(jobId: string, entry: JobLogEntryApi): LogEntry {
  return {
    time: localTime(entry.time),
    level: toLevel(entry.level),
    msg: entry.message,
    source: "job",
    jobId,
    seq: entry.seq,
    stageId: entry.stage_id,
  };
}
