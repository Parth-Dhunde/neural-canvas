// Backend availability state machine. Runtime-import free so it can run under node --test.
//
// A single failed health check never marks the backend offline: the indicator switches to
// "checking" and retries quickly; only `failuresBeforeOffline` consecutive failures confirm
// that the backend is offline. One success always restores "connected".

export type HealthPhase = "checking" | "connected" | "disconnected";

export interface HealthTracker {
  phase: HealthPhase;
  consecutiveFailures: number;
}

export const HEALTH_TIMING = {
  /** Recheck interval while connected. */
  connectedIntervalMs: 15_000,
  /** Quick retry after a failure, before offline is confirmed. */
  retryIntervalMs: 2_500,
  /** First recheck interval once offline; doubles up to the maximum. */
  offlineIntervalMs: 10_000,
  offlineMaxIntervalMs: 20_000,
  /** Consecutive failures needed to confirm the backend is offline. */
  failuresBeforeOffline: 3,
  /** Per-request timeout for GET /health. */
  requestTimeoutMs: 5_000,
} as const;

export function initialHealthTracker(): HealthTracker {
  return { phase: "checking", consecutiveFailures: 0 };
}

export function recordHealthResult(
  tracker: HealthTracker,
  ok: boolean,
  timing: typeof HEALTH_TIMING = HEALTH_TIMING,
): HealthTracker {
  if (ok) return { phase: "connected", consecutiveFailures: 0 };
  const consecutiveFailures = tracker.consecutiveFailures + 1;
  const phase: HealthPhase =
    tracker.phase === "disconnected" || consecutiveFailures >= timing.failuresBeforeOffline
      ? "disconnected"
      : "checking";
  return { phase, consecutiveFailures };
}

/** Delay before the next health check. */
export function nextHealthDelayMs(
  tracker: HealthTracker,
  timing: typeof HEALTH_TIMING = HEALTH_TIMING,
): number {
  if (tracker.phase === "connected") return timing.connectedIntervalMs;
  if (tracker.phase === "checking") return timing.retryIntervalMs;
  const extra = Math.max(0, tracker.consecutiveFailures - timing.failuresBeforeOffline);
  return Math.min(timing.offlineIntervalMs * 2 ** extra, timing.offlineMaxIntervalMs);
}
