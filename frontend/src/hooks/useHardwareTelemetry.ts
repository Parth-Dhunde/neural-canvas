import { useEffect } from "react";
import { getHardware } from "@/services/hardware";
import { useAppStore } from "@/store/useAppStore";

const TELEMETRY_POLL_MS = 1500;

/** Poll live hardware telemetry while the caller route is mounted. */
export function useHardwareTelemetry(enabled: boolean) {
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const backendStatus = useAppStore((s) => s.backendHealth.status);
  const setHardware = useAppStore((s) => s.setHardware);

  useEffect(() => {
    if (!enabled || backendStatus !== "connected") {
      return;
    }

    let cancelled = false;

    const poll = async () => {
      const hardware = await getHardware(backendUrl);
      if (!cancelled && hardware) {
        setHardware(hardware);
      }
    };

    void poll();
    const intervalId = window.setInterval(() => void poll(), TELEMETRY_POLL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [backendUrl, backendStatus, enabled, setHardware]);
}
