import { useEffect } from "react";
import { getJob } from "@/services/jobs";
import { getJobLogs, mapJobLogEntry } from "@/services/logs";
import { getPipelineSnapshot } from "@/services/pipeline";
import { selectUnseenEntries } from "@/lib/terminalLog";
import { useAppStore } from "@/store/useAppStore";
import type { PipelineStep } from "@/types";

const ACTIVE_POLL_MS = 1000;
const IDLE_POLL_MS = 5000;
const ERROR_POLL_MS = 4000;
const INITIAL_TAIL = 500;
const PAGE_LIMIT = 1000;
const MAX_PAGES_PER_TICK = 5;

function pipelineSignature(steps: PipelineStep[]): string {
  return steps.map((s) => `${s.id}:${s.status}:${s.progress}`).join("|");
}

/**
 * Poll pipeline state and job logs for the active job.
 *
 * Polls quickly while a stage runs (or this tab awaits a run request) and slowly when idle,
 * so runs started elsewhere (e.g. via curl) still show up. Logs are fetched incrementally
 * with a sequence cursor, so each poll only transfers new lines.
 */
export function usePipelineActivity() {
  const jobId = useAppStore((s) => s.currentJob?.id ?? null);
  const backendUrl = useAppStore((s) => s.settings.backendUrl);

  useEffect(() => {
    const store = useAppStore.getState;
    store().removeJobTerminalLines();

    if (!jobId) {
      store().setPipelineExecution(null);
      store().setLogStream({ status: "no-job", jobId: null, error: null, truncated: false });
      return;
    }

    store().setLogStream({ status: "loading", jobId, error: null, truncated: false });

    let cancelled = false;
    let timer: number | undefined;
    let inFlight = false;
    let wakeRequested = false;
    let cursor: number | null = null;
    // Highest seq appended to the terminal for this job; drops any re-delivered entries.
    let lastAppendedSeq = 0;
    let wasActive = false;

    const schedule = (delay: number) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void tick(), delay);
    };

    const fetchLogs = async () => {
      for (let page = 0; page < MAX_PAGES_PER_TICK; page += 1) {
        const response =
          cursor === null
            ? await getJobLogs(jobId, { tail: INITIAL_TAIL }, backendUrl)
            : await getJobLogs(jobId, { after: cursor, limit: PAGE_LIMIT }, backendUrl);
        if (cancelled) return;

        if (response.reset) {
          // Backend log restarted behind our cursor: reload the tail from scratch.
          store().removeJobTerminalLines();
          cursor = null;
          lastAppendedSeq = 0;
          continue;
        }

        cursor = response.next_after;
        const fresh = selectUnseenEntries(response.entries, lastAppendedSeq);
        if (fresh.length > 0) lastAppendedSeq = fresh[fresh.length - 1].seq;
        store().appendTerminalLines(fresh.map((entry) => mapJobLogEntry(jobId, entry)));
        if (response.truncated) store().setLogStream({ truncated: true });
        if (!response.has_more) return;
      }
    };

    const tick = async () => {
      if (cancelled) return;
      if (inFlight) {
        wakeRequested = true;
        return;
      }

      const backendStatus = store().backendHealth.status;
      if (backendStatus === "disconnected" || backendStatus === "error") {
        store().setLogStream({ status: "disconnected", error: null });
        schedule(ERROR_POLL_MS);
        return;
      }

      inFlight = true;
      let delay = IDLE_POLL_MS;
      try {
        const snapshot = await getPipelineSnapshot(jobId, backendUrl);
        if (cancelled) return;

        const state = store();
        if (state.currentJob?.id === jobId) {
          if (pipelineSignature(snapshot.steps) !== pipelineSignature(state.pipeline)) {
            state.setPipeline(snapshot.steps);
          }
          state.setPipelineExecution(snapshot.execution);
        }

        await fetchLogs();
        if (cancelled) return;

        const active =
          snapshot.execution?.status === "running" ||
          snapshot.steps.some((step) => step.status === "running") ||
          store().pipelineRequestActive;

        if (wasActive && !active) {
          // A run just finished (possibly started elsewhere): refresh job metadata such as mesh_path.
          const job = await getJob(jobId, backendUrl);
          if (!cancelled && job && store().currentJob?.id === jobId) {
            const { jobs, setJobs, setCurrentJob } = store();
            setJobs(jobs.map((entry) => (entry.id === job.id ? job : entry)));
            setCurrentJob(job);
          }
        }
        wasActive = active;

        store().setLogStream({ status: active ? "live" : "idle", jobId, error: null });
        delay = active ? ACTIVE_POLL_MS : IDLE_POLL_MS;
      } catch (error) {
        if (cancelled) return;
        if (error instanceof TypeError) {
          // fetch() rejects with TypeError when the backend is unreachable (network failure).
          store().setLogStream({ status: "disconnected", error: null });
        } else {
          const message = error instanceof Error ? error.message : "Unknown error";
          store().setLogStream({ status: "error", error: message });
        }
        delay = ERROR_POLL_MS;
      } finally {
        inFlight = false;
      }

      if (cancelled) return;
      if (wakeRequested) {
        wakeRequested = false;
        schedule(0);
      } else {
        schedule(delay);
      }
    };

    // Start/finish of a run request in this tab: poll right away instead of waiting.
    const unsubscribe = useAppStore.subscribe((state, previous) => {
      if (state.pipelineRequestActive !== previous.pipelineRequestActive) schedule(0);
    });

    void tick();

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      unsubscribe();
    };
  }, [jobId, backendUrl]);
}
