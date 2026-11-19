import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import { StatusBadge } from "@/components/ui-pro/StatusBadge";
import { ProgressBar } from "@/components/ui-pro/ProgressBar";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";
import type { LogEntry } from "@/types";

const STAGE_LOG_PREVIEW_LINES = 60;

export function Pipeline() {
  const pipeline = useAppStore((s) => s.pipeline);
  const lines = useAppStore((s) => s.terminal.lines);
  const [expanded, setExpanded] = useState<number | null>(null);

  const expandedLogs = useMemo<LogEntry[]>(() => {
    if (expanded === null) return [];
    return lines
      .filter((l) => l.source === "job" && l.stageId === expanded)
      .slice(-STAGE_LOG_PREVIEW_LINES);
  }, [expanded, lines]);

  return (
    <div className="flex flex-col">
      <div className="grid grid-cols-4 gap-2 px-1 pb-3 sm:grid-cols-7">
        {pipeline.map((s) => (
          <div key={s.id} className="flex min-w-0 flex-col items-center gap-1.5">
            <div
              className={cn(
                "mono relative flex h-9 w-full items-center justify-center overflow-hidden rounded-sm border text-[11px] font-medium",
                s.status === "completed" && "border-success/40 bg-success/10 text-success",
                s.status === "running" && "border-bronze/60 bg-bronze/10 text-bronze",
                (s.status === "waiting" || s.status === "queued") &&
                  "border-border bg-surface-2 text-muted-foreground",
                s.status === "failed" && "border-destructive/50 bg-destructive/10 text-destructive",
                s.status === "cancelled" && "border-border bg-surface-3 text-muted-foreground",
              )}
            >
              {s.status === "running" && (
                <>
                  <span
                    className="absolute inset-y-0 left-0 bg-bronze/15 transition-[width] duration-500"
                    style={{ width: `${Math.min(100, Math.max(0, s.progress))}%` }}
                  />
                  <span className="nc-shimmer absolute inset-0" />
                </>
              )}
              <span className="relative">{String(s.id).padStart(2, "0")}</span>
            </div>
            <div
              className="w-full truncate text-center text-[10px] uppercase tracking-wider text-muted-foreground"
              title={s.name}
            >
              {s.name}
            </div>
          </div>
        ))}
      </div>

      <div className="hairline-t">
        {pipeline.map((s) => {
          const open = expanded === s.id;
          return (
            <div key={s.id} className="hairline-b last:border-b-0">
              <button
                onClick={() => setExpanded(open ? null : s.id)}
                aria-expanded={open}
                className="grid w-full grid-cols-[20px_minmax(0,1fr)_auto] items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-surface-2/70 md:grid-cols-[20px_200px_minmax(0,1fr)_120px]"
              >
                <ChevronRight
                  className={cn(
                    "h-3.5 w-3.5 text-subtle transition-transform",
                    open && "rotate-90",
                  )}
                />
                <div className="flex min-w-0 items-center gap-2">
                  <span className="mono text-[11px] text-subtle">
                    {String(s.id).padStart(2, "0")}
                  </span>
                  <span className="truncate text-[13px] text-ivory">{s.name}</span>
                </div>
                <div className="hidden items-center gap-3 md:flex">
                  <ProgressBar
                    value={s.progress}
                    className="w-full max-w-56"
                    tone={
                      s.status === "failed"
                        ? "destructive"
                        : s.status === "completed"
                          ? "success"
                          : "bronze"
                    }
                  />
                  <span className="mono w-9 text-right text-[11px] text-muted-foreground">
                    {s.progress}%
                  </span>
                </div>
                <StatusBadge status={s.status} className="justify-self-end" />
              </button>
              {open && (
                <div className="mono terminal-body max-h-56 overflow-auto border-t border-border/60 px-6 py-3 text-[11px] leading-relaxed select-text">
                  {expandedLogs.length === 0 ? (
                    <div className="text-muted-foreground">
                      No log lines for this stage in the current view.
                    </div>
                  ) : (
                    expandedLogs.map((l) => (
                      <div key={`${l.jobId}-${l.seq}`} className="flex gap-3">
                        <span className="w-16 shrink-0 text-subtle">{l.time}</span>
                        <span
                          className={cn(
                            "w-10 shrink-0 uppercase",
                            l.level === "ok" && "text-success",
                            l.level === "warn" && "text-warning",
                            l.level === "error" && "text-destructive",
                            l.level === "info" && "text-subtle",
                          )}
                        >
                          {l.level}
                        </span>
                        <span className="min-w-0 flex-1 break-words text-foreground/90">
                          {l.msg}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
