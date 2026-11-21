import { useEffect, useRef, useState } from "react";
import { ChevronDown, Layers3 } from "lucide-react";
import { WipBadge } from "@/components/ui-pro/WipBadge";
import { ENGINE_OPTIONS, isSubmittableEngine } from "@/lib/engines";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";

/**
 * Engine selector. Work-in-progress engines are listed with a badge and an explanation but
 * cannot be selected, so no job can be submitted with them.
 */
export function EnginePicker({
  align = "left",
  className,
}: {
  align?: "left" | "right";
  className?: string;
}) {
  const selectedEngine = useAppStore((s) => s.selectedEngine);
  const setSelectedEngine = useAppStore((s) => s.setSelectedEngine);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Engine: ${selectedEngine}`}
        className="flex h-8 items-center gap-2 rounded-sm border border-border bg-surface-2 px-2.5 text-[12px] hover:border-border-strong"
      >
        <Layers3 className="h-3.5 w-3.5 text-bronze" strokeWidth={1.6} />
        <span className="text-ivory">{selectedEngine}</span>
        <ChevronDown className="h-3 w-3 text-subtle" />
      </button>
      {open && (
        <div
          role="listbox"
          aria-label="Reconstruction engine"
          className={cn(
            "absolute top-9 z-50 w-72 rounded-sm border border-border bg-popover p-1 shadow-2xl",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {ENGINE_OPTIONS.map((option) => {
            const available = isSubmittableEngine(option.id);
            const active = option.id === selectedEngine;
            return (
              <button
                key={option.id}
                type="button"
                role="option"
                aria-selected={active}
                aria-disabled={!available}
                disabled={!available}
                onClick={() => {
                  if (!isSubmittableEngine(option.id)) return;
                  setSelectedEngine(option.id);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full flex-col gap-1 rounded-sm px-2.5 py-2 text-left disabled:cursor-not-allowed",
                  active ? "bg-selected/10" : available && "hover:bg-surface-2",
                )}
              >
                <span className="flex items-center justify-between gap-2 text-[12px]">
                  <span className={available ? "text-ivory" : "text-subtle"}>{option.id}</span>
                  {active ? (
                    <span className="mono text-[10px] text-bronze">ACTIVE</span>
                  ) : available ? (
                    <span className="mono text-[10px] text-success">AVAILABLE</span>
                  ) : (
                    <WipBadge />
                  )}
                </span>
                <span className="text-[11px] leading-snug text-muted-foreground">
                  {option.description}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
