import { apiFetch } from "./api";

/** A median over valid measurements; `value` is null when `sample_size` is 0. */
export interface MedianStatisticApi {
  statistic: "median";
  value: number | null;
  unit: string;
  sample_size: number;
  unavailable_reason: string | null;
}

export interface EngineStatsApi {
  completed_jobs: number;
  median_psnr_db: MedianStatisticApi;
  median_training_seconds: MedianStatisticApi;
  median_peak_vram_mib: MedianStatisticApi;
}

/** An experiment record from outputs/experiments — never part of production statistics. */
export interface ExperimentalBenchmarkApi {
  experiment: string;
  group: string;
  record: string;
  status: string | null;
  psnr_mean_db: number | null;
  baseline_psnr_mean_db: number | null;
  frames_evaluated: number | null;
  training_seconds: number | null;
  peak_vram_mib: number | null;
  final_loss: number | null;
}

export interface DashboardSummaryApi {
  generated_at: string;
  jobs: {
    total: number;
    active: number;
    active_statuses: string[];
    completed_total: number;
    completed_7d: number;
    failed: number;
  };
  training: MedianStatisticApi;
  storage: { bytes: number; scope: string };
  engines: Record<string, EngineStatsApi>;
  experimental: ExperimentalBenchmarkApi[];
}

/** GET /api/dashboard/summary */
export async function getDashboardSummary(baseUrl?: string): Promise<DashboardSummaryApi> {
  return apiFetch<DashboardSummaryApi>("/api/dashboard/summary", { baseUrl });
}
