import { useState } from "react";
import { Search, ChevronDown, Activity, Layers3, Menu, X } from "lucide-react";
import { BackendStatusBadge } from "./BackendStatusBadge";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { SUPPORTED_ENGINES } from "@/lib/constants";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";

export function Topbar({
  navOpen = false,
  onToggleNav,
}: {
  navOpen?: boolean;
  onToggleNav?: () => void;
}) {
  const selectedEngine = useAppStore((s) => s.selectedEngine);
  const setSelectedEngine = useAppStore((s) => s.setSelectedEngine);
  const currentJob = useAppStore((s) => s.currentJob);
  const pipeline = useAppStore((s) => s.pipeline);
  const [engineOpen, setEngineOpen] = useState(false);

  const activeStep = pipeline.find((s) => s.status === "running");
  const completedSteps = pipeline.filter((s) => s.status === "completed").length;
  const failedStep = pipeline.find((s) => s.status === "failed");
  const idleLabel =
    pipeline.length > 0 && completedSteps === pipeline.length
      ? "Complete"
      : failedStep
        ? `Stage ${failedStep.id} failed`
        : "Waiting";

  return (
    <header className="hairline-b relative z-50 flex h-12 shrink-0 items-center gap-2 nc-topbar nc-chrome px-2 sm:gap-3 sm:px-3">
      <button
        type="button"
        onClick={onToggleNav}
        aria-label={navOpen ? "Close navigation" : "Open navigation"}
        aria-expanded={navOpen}
        aria-controls="app-navigation"
        className="grid h-8 w-8 shrink-0 place-items-center rounded-sm text-muted-foreground hover:bg-surface-2 hover:text-ivory lg:hidden"
      >
        {navOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
      </button>
      <div className="hidden items-center gap-2 pl-1 lg:flex">
        <div className="flex gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full bg-destructive/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-warning/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-success/70" />
        </div>
      </div>

      <div className="hairline-l hidden h-6 lg:block" />

      <div className="flex min-w-0 items-center gap-2">
        <span className="label-caps hidden sm:inline">Job</span>
        <div className="flex min-w-0 items-center gap-2 rounded-sm border border-border bg-surface-2 px-2.5 py-1">
          {currentJob ? (
            <>
              <span
                className={cn(
                  "h-1.5 w-1.5 shrink-0 rounded-full",
                  activeStep ? "nc-live-dot bg-bronze" : "bg-subtle",
                )}
              />
              <span className="mono truncate text-[12px] text-ivory">{currentJob.id}</span>
              <span className="hidden truncate text-[12px] text-muted-foreground md:inline">
                / {currentJob.name}
              </span>
            </>
          ) : (
            <span className="mono text-[12px] text-muted-foreground">No active job</span>
          )}
        </div>
      </div>

      <div className="relative hidden sm:block">
        <button
          onClick={() => setEngineOpen((v) => !v)}
          aria-haspopup="listbox"
          aria-expanded={engineOpen}
          className="flex items-center gap-2 rounded-sm border border-border bg-surface-2 px-2.5 py-1 text-[12px] hover:border-border-strong"
        >
          <Layers3 className="h-3.5 w-3.5 text-bronze" strokeWidth={1.6} />
          <span className="text-ivory">{selectedEngine}</span>
          <ChevronDown className="h-3 w-3 text-subtle" />
        </button>
        {engineOpen && (
          <div className="absolute left-0 top-9 z-30 w-56 rounded-sm border border-border bg-popover p-1 shadow-2xl">
            {SUPPORTED_ENGINES.map((e) => (
              <button
                key={e}
                onClick={() => {
                  setSelectedEngine(e);
                  setEngineOpen(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between rounded-sm px-2 py-1.5 text-left text-[12px]",
                  e === selectedEngine
                    ? "bg-selected/10 text-ivory"
                    : "text-muted-foreground hover:bg-surface-2",
                )}
              >
                <span>{e}</span>
                {e === selectedEngine && (
                  <span className="mono text-[10px] text-bronze">ACTIVE</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="hidden items-center gap-2 rounded-sm border border-border bg-surface-2 px-2.5 py-1 md:flex">
        <Activity className="h-3.5 w-3.5 text-subtle" strokeWidth={1.6} />
        <span className="label-caps !text-[9px]">Step</span>
        {activeStep ? (
          <>
            <span className="mono text-[12px] text-ivory">
              {activeStep.id} / {pipeline.length} · {activeStep.name}
            </span>
            <span className="mono text-[10px] text-subtle">{activeStep.progress}%</span>
          </>
        ) : (
          <span className="mono text-[12px] text-muted-foreground">
            {completedSteps} / {pipeline.length} · {idleLabel}
          </span>
        )}
      </div>

      <div className="flex-1" />

      <div className="relative hidden w-72 lg:block">
        <Search
          className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
          strokeWidth={1.6}
        />
        <input
          disabled
          title="Search is not implemented yet"
          aria-label="Search (not implemented yet)"
          placeholder="Search — coming soon"
          className="mono h-8 w-full rounded-sm border border-border bg-surface-2 pl-8 pr-2 text-[12px] text-ivory placeholder:text-subtle focus:border-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
        />
      </div>

      <BackendStatusBadge />

      <ThemeSwitcher />
    </header>
  );
}
