import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Search, Activity, Menu, X } from "lucide-react";
import { BackendStatusBadge } from "./BackendStatusBadge";
import { EnginePicker } from "./EnginePicker";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";

export function Topbar({
  navOpen = false,
  onToggleNav,
}: {
  navOpen?: boolean;
  onToggleNav?: () => void;
}) {
  const currentJob = useAppStore((s) => s.currentJob);
  const pipeline = useAppStore((s) => s.pipeline);
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

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

      <EnginePicker className="hidden sm:block" />

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

      <form
        role="search"
        className="relative hidden w-72 lg:block"
        onSubmit={(event) => {
          event.preventDefault();
          const q = query.trim();
          void navigate({ to: "/jobs", search: q ? { q } : {} });
        }}
      >
        <Search
          className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
          strokeWidth={1.6}
        />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search jobs (opens the Jobs page)"
          placeholder="Search jobs… (Enter)"
          className="mono h-8 w-full rounded-sm border border-border bg-surface-2 pl-8 pr-2 text-[12px] text-ivory placeholder:text-subtle focus:border-ring focus:outline-none"
        />
      </form>

      <BackendStatusBadge />

      <ThemeSwitcher />
    </header>
  );
}
