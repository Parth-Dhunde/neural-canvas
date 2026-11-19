import { cn } from "@/lib/utils";

export function ProgressBar({
  value,
  className,
  tone = "bronze",
}: {
  value: number;
  className?: string;
  tone?: "bronze" | "success" | "warning" | "destructive";
}) {
  const toneMap = {
    bronze: "bg-gradient-to-r from-bronze-muted to-bronze",
    success: "bg-success",
    warning: "bg-warning",
    destructive: "bg-destructive",
  };
  return (
    <div className={cn("h-1 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div
        className={cn("h-full transition-all duration-500", toneMap[tone])}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
