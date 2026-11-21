import { cn } from "@/lib/utils";

/** Visible marker for planned features that cannot be used yet. */
export function WipBadge({
  label = "Work in progress",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-sm border border-warning/50 bg-warning/10 px-1.5 py-px text-[9px] font-medium tracking-widest text-warning uppercase",
        className,
      )}
    >
      {label}
    </span>
  );
}
