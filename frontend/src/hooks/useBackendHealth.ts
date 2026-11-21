import { useEffect } from "react";
import {
  initialHealthTracker,
  nextHealthDelayMs,
  recordHealthResult,
  type HealthTracker,
} from "@/lib/backendStatus";
import { onBackendUnreachable } from "@/services/api";
import { fetchBackendDetails, offlineHealth, pingHealth } from "@/services/health";
import { useAppStore } from "@/store/useAppStore";

/**
 * Track backend availability with GET /health.
 *
 * - Checks on load, then every 15 s while connected.
 * - A failed check shows "Checking" and retries after 2.5 s; three consecutive failures
 *   confirm "Disconnected", after which checks back off from 10 s to 20 s.
 * - Paused while the tab is hidden; rechecks immediately when it becomes visible, when the
 *   browser comes back online, and when any API request fails to reach the backend.
 */
export function useBackendHealth() {
  const backendUrl = useAppStore((s) => s.settings.backendUrl);

  useEffect(() => {
    const store = useAppStore.getState;
    let tracker: HealthTracker = initialHealthTracker();
    let timer: number | undefined;
    let inFlight = false;
    let disposed = false;

    store().setBackendHealth({ ...offlineHealth(backendUrl), status: "connecting" });

    const schedule = (delay: number) => {
      window.clearTimeout(timer);
      if (disposed || document.visibilityState === "hidden") return;
      timer = window.setTimeout(() => void check(), delay);
    };

    const check = async () => {
      if (disposed || inFlight) return;
      inFlight = true;
      const ok = await pingHealth(backendUrl);
      inFlight = false;
      if (disposed) return;
      const previous = tracker.phase;
      tracker = recordHealthResult(tracker, ok);

      if (tracker.phase === "connected") {
        store().setBackendHealth({
          status: "connected",
          url: backendUrl,
          lastHeartbeat: new Date().toISOString(),
        });
        if (previous !== "connected") {
          const details = await fetchBackendDetails(backendUrl);
          if (!disposed) store().setBackendHealth(details);
        }
      } else if (tracker.phase === "checking") {
        store().setBackendStatus("connecting");
      } else {
        store().setBackendHealth(offlineHealth(backendUrl));
      }
      schedule(nextHealthDelayMs(tracker));
    };

    const checkNow = () => {
      window.clearTimeout(timer);
      void check();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") checkNow();
      else window.clearTimeout(timer);
    };

    void check();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("online", checkNow);
    window.addEventListener("offline", checkNow);
    // A failed API request while connected suggests a drop: check at once. While already
    // checking or offline, keep the normal retry/backoff schedule.
    const unsubscribe = onBackendUnreachable(() => {
      if (tracker.phase === "connected") checkNow();
    });

    return () => {
      disposed = true;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("online", checkNow);
      window.removeEventListener("offline", checkNow);
      unsubscribe();
    };
  }, [backendUrl]);
}
