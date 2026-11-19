import { cn } from "@/lib/utils";
import type { JobStatus, PipelineStepStatus } from "@/types";

type BadgeStatus = JobStatus | PipelineStepStatus;

export function StatusBadge({ status, className }: { status: BadgeStatus; className?: string }) {
  const map: Record<string, { label: string; dot: string; text: string; bg: string }> = {
    waiting: {
      label: "Waiting",
      dot: "bg-subtle",
      text: "text-subtle",
      bg: "bg-surface-3",
    },
    running: {
      label: "Running",
      dot: "bg-bronze",
      text: "text-bronze",
      bg: "bg-bronze/10",
    },
    completed: {
      label: "Completed",
      dot: "bg-success",
      text: "text-success",
      bg: "bg-success/10",
    },
    failed: {
      label: "Failed",
      dot: "bg-destructive",
      text: "text-destructive",
      bg: "bg-destructive/10",
    },
    queued: {
      label: "Queued",
      dot: "bg-subtle",
      text: "text-subtle",
      bg: "bg-surface-3",
    },
    cancelled: {
      label: "Cancelled",
      dot: "bg-subtle",
      text: "text-muted-foreground",
      bg: "bg-surface-3",
    },
    paused: {
      label: "Paused",
      dot: "bg-warning",
      text: "text-warning",
      bg: "bg-warning/10",
    },
  };
  const s = map[status] ?? map.waiting;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-widest",
        s.bg,
        s.text,
        className,
      )}
    >
      <span
        className={cn("h-1.5 w-1.5 rounded-full", s.dot, status === "running" && "nc-live-dot")}
      />
      {s.label}
    </span>
  );
}
