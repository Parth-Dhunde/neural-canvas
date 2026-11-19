import { useCallback, useEffect, useState } from "react";
import { getJobExports, type ExportManifestApi } from "@/services/exports";
import { useAppStore } from "@/store/useAppStore";

export type ExportsStatus = "idle" | "loading" | "ready" | "error";

/**
 * Verified mesh manifest for a job. Re-fetches when the job's mesh stages (5–7) change, so the
 * viewer switches to the cleaned mesh as soon as cleanup and export finish.
 */
export function useJobExports(jobId: string | null) {
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const meshStagesKey = useAppStore((s) =>
    s.currentJob?.id === jobId
      ? s.pipeline
          .filter((step) => step.id >= 5)
          .map((step) => `${step.id}:${step.status}`)
          .join("|")
      : "",
  );
  const [manifest, setManifest] = useState<ExportManifestApi | null>(null);
  const [status, setStatus] = useState<ExportsStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!jobId) {
      setManifest(null);
      setStatus("idle");
      setError(null);
      return;
    }
    let cancelled = false;
    setStatus("loading");
    setError(null);
    getJobExports(jobId, backendUrl)
      .then((data) => {
        if (cancelled) return;
        setManifest(data);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setManifest(null);
        setError(err instanceof Error ? err.message : "Could not load mesh exports");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, backendUrl, meshStagesKey, reloadToken]);

  const reload = useCallback(() => setReloadToken((n) => n + 1), []);
  return { manifest, status, error, reload };
}
