import { type ReactNode, useEffect, useState } from "react";
import { useRouterState } from "@tanstack/react-router";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { Terminal } from "./Terminal";
import { BackendOfflineBanner } from "./BackendNotices";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import { usePersistedSettings } from "@/hooks/usePersistedSettings";
import { useJobsSync } from "@/hooks/useJobsSync";
import { usePipelineActivity } from "@/hooks/usePipelineActivity";
import { useSidebarLayout } from "@/hooks/useSidebarLayout";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";
import { Toaster } from "@/components/ui/sonner";

const BACKEND_STATUS_LABELS: Record<string, string> = {
  connected: "connected",
  connecting: "checking",
  disconnected: "offline",
  error: "error",
};

// Fixed rather than `new Date().getFullYear()`, so server and client render the same text.
const COPYRIGHT_YEAR = 2026;

export function DesktopShell({ children }: { children: ReactNode }) {
  usePersistedSettings();
  useBackendHealth();
  useJobsSync();
  usePipelineActivity();
  const terminalOpen = useAppStore((s) => s.terminal.open);
  const terminalHeight = useAppStore((s) => s.terminal.height);
  const setTerminal = useAppStore((s) => s.setTerminal);
  const selectedEngine = useAppStore((s) => s.selectedEngine);
  const backendHealth = useAppStore((s) => s.backendHealth);
  const hardware = useAppStore((s) => s.hardware);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [navOpen, setNavOpen] = useState(false);
  const sidebarLayout = useSidebarLayout();

  // The drawer (below lg) closes on navigation and on Escape.
  useEffect(() => setNavOpen(false), [pathname]);
  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-background text-foreground select-none">
      <Topbar navOpen={navOpen} onToggleNav={() => setNavOpen((open) => !open)} />
      <div className="relative flex min-h-0 flex-1">
        <Sidebar mobileOpen={navOpen} onClose={() => setNavOpen(false)} layout={sidebarLayout} />
        <div className="flex min-w-0 flex-1 flex-col">
          <BackendOfflineBanner />
          <main className={cn("relative min-h-0 flex-1 overflow-auto", "nc-ambient nc-noise")}>
            {children}
          </main>
          <Terminal
            open={terminalOpen}
            onToggle={() => setTerminal({ open: !terminalOpen })}
            height={terminalHeight}
            onResize={(h) => setTerminal({ height: h })}
          />
        </div>
      </div>
      <StatusBar
        engine={selectedEngine}
        backendStatus={backendHealth.status}
        hardwareStatus={hardware.status}
        hardwareMemory={hardware.memory}
      />
      <Toaster />
    </div>
  );
}

function StatusBar({
  engine,
  backendStatus,
  hardwareStatus,
  hardwareMemory,
}: {
  engine: string;
  backendStatus: string;
  hardwareStatus: string;
  hardwareMemory: string;
}) {
  return (
    // Below sm the credit wraps onto a second line instead of being clipped; from sm up the
    // bar keeps its single 24px row.
    <footer className="hairline-t nc-topbar nc-chrome nc-chrome-footer flex min-h-6 shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-0.5 overflow-hidden px-3 py-1 text-[10px] tracking-widest whitespace-nowrap text-subtle uppercase sm:h-6 sm:flex-nowrap sm:py-0">
      <div className="flex min-w-0 items-center gap-4">
        <span className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-block h-1.5 w-1.5 rounded-full",
              backendStatus === "connected"
                ? "bg-success"
                : backendStatus === "connecting"
                  ? "nc-live-dot bg-warning"
                  : "bg-subtle",
            )}
          />
          Backend {BACKEND_STATUS_LABELS[backendStatus] ?? backendStatus}
        </span>
        <span className="hidden sm:inline">Engine — {engine}</span>
        <span className="hidden md:inline">{hardwareStatus}</span>
      </div>
      <div className="flex min-w-0 items-center gap-3">
        {/* Live telemetry from GET /api/hardware (refreshed while the dashboard is open). */}
        <div className="hidden min-w-0 truncate md:block">{hardwareMemory}</div>
        <span aria-hidden className="hairline-l hidden h-3 md:block" />
        <Attribution />
      </div>
    </footer>
  );
}

/** Creator credit; sentence case so it reads as a signature, not another status readout. */
function Attribution() {
  return (
    <p className="shrink-0 text-[10.5px] tracking-normal text-muted-foreground normal-case">
      © {COPYRIGHT_YEAR} Parth Dhunde
    </p>
  );
}
