import { Info, PlugZap } from "lucide-react";
import { OWNER_CONTACT_EMAIL } from "@/lib/constants";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";

export const LOCAL_BACKEND_NOTICE =
  "NeuralCanvas uses a locally hosted backend for 3D reconstruction. The backend runs on the project owner's laptop, so processing services may not always be available. Please be aware that the backend must be running for reconstruction jobs and other backend-dependent features to work.";

/** Always-visible, informational (not an error): reconstruction depends on the owner's laptop. */
export function LocalBackendNotice({ className }: { className?: string }) {
  return (
    <aside
      aria-label="About the local backend"
      className={cn(
        "flex items-start gap-3 rounded-sm border border-border bg-surface-2/60 px-3.5 py-2.5",
        className,
      )}
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" strokeWidth={1.7} aria-hidden />
      <p className="text-[12px] leading-relaxed text-muted-foreground">{LOCAL_BACKEND_NOTICE}</p>
    </aside>
  );
}

/** Shown only while the backend is confirmed offline; disappears when it reconnects. */
export function BackendOfflineBanner() {
  const status = useAppStore((s) => s.backendHealth.status);
  if (status !== "disconnected") return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="hairline-b flex shrink-0 items-start gap-3 border-warning/40 bg-warning/8 px-4 py-2.5 sm:px-6"
    >
      <PlugZap className="mt-0.5 h-4 w-4 shrink-0 text-warning" strokeWidth={1.7} aria-hidden />
      <div className="min-w-0 space-y-1 text-[12px] leading-relaxed">
        <p className="text-ivory">
          NeuralCanvas&apos;s local backend is currently offline. Reconstruction services are
          unavailable because the backend runs on the project owner&apos;s laptop and is not
          currently connected.
        </p>
        <p className="text-muted-foreground">
          If you need the backend enabled for your work, you can contact the project owner at{" "}
          <a
            href={`mailto:${OWNER_CONTACT_EMAIL}`}
            className="select-text text-bronze underline-offset-2 hover:underline"
          >
            {OWNER_CONTACT_EMAIL}
          </a>
          . Pages, the Guide and other information remain available; the status reconnects
          automatically.
        </p>
      </div>
    </div>
  );
}
