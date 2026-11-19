import { useEffect, useRef } from "react";
import { refreshJobList, syncJobsFromBackend } from "@/lib/jobActions";
import { useAppStore } from "@/store/useAppStore";

const JOB_LIST_REFRESH_MS = 15_000;

/**
 * Load jobs from the backend when connectivity is established, then keep their status and
 * progress current (backend-derived) while connected.
 */
export function useJobsSync() {
  const backendStatus = useAppStore((s) => s.backendHealth.status);
  const syncedRef = useRef(false);

  useEffect(() => {
    if (backendStatus !== "connected") {
      syncedRef.current = false;
      return;
    }

    if (!syncedRef.current) {
      syncedRef.current = true;
      void syncJobsFromBackend();
    }
    const timer = window.setInterval(() => void refreshJobList(), JOB_LIST_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [backendStatus]);
}
