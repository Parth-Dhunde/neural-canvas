import { useEffect } from "react";
import { healthCheck } from "@/services/health";
import { useAppStore } from "@/store/useAppStore";

const POLL_INTERVAL_MS = 30_000;

/**
 * Poll GET /health and update the global backend status indicator.
 */
export function useBackendHealth() {
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const setBackendStatus = useAppStore((s) => s.setBackendStatus);
  const setBackendHealth = useAppStore((s) => s.setBackendHealth);
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      setBackendStatus("connecting");
      const health = await healthCheck(backendUrl);
      if (!cancelled) {
        setBackendHealth(health);
      }
    };

    void poll();
    const intervalId = window.setInterval(() => void poll(), POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [backendUrl, setBackendHealth, setBackendStatus]);
}
