import { useEffect, useState } from "react";
import { jobsSignature } from "@/lib/dashboardStats";
import { getDashboardSummary, type DashboardSummaryApi } from "@/services/dashboard";
import { useAppStore } from "@/store/useAppStore";

const REFRESH_MS = 30_000;

export interface DashboardSummaryState {
  summary: DashboardSummaryApi | null;
  error: string | null;
}

/**
 * Load GET /api/dashboard/summary while the dashboard is open.
 *
 * Refetches whenever any job's status or progress changes (e.g. when usePipelineActivity
 * refreshes a job after its run finishes), and every 30s for runs started elsewhere.
 */
export function useDashboardSummary(): DashboardSummaryState {
  const backendStatus = useAppStore((s) => s.backendHealth.status);
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const signature = useAppStore((s) => jobsSignature(s.jobs));
  const [state, setState] = useState<DashboardSummaryState>({ summary: null, error: null });

  useEffect(() => {
    if (backendStatus !== "connected") return;
    let cancelled = false;

    const load = async () => {
      try {
        const summary = await getDashboardSummary(backendUrl);
        if (!cancelled) setState({ summary, error: null });
      } catch (error) {
        if (!cancelled) {
          const message = error instanceof Error ? error.message : "Unknown error";
          setState((previous) => ({ summary: previous.summary, error: message }));
        }
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), REFRESH_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [backendStatus, backendUrl, signature]);

  return state;
}
