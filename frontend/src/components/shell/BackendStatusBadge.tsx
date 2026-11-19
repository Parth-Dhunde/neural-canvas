import { useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useAppStore } from "@/store/useAppStore";
import type { BackendConnectionStatus, ComponentStatus } from "@/types";
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<
  BackendConnectionStatus,
  { label: string; dot: string; emoji: string }
> = {
  connected: { label: "Connected", dot: "bg-success", emoji: "🟢" },
  connecting: { label: "Connecting", dot: "bg-warning nc-live-dot", emoji: "🟡" },
  disconnected: { label: "Disconnected", dot: "bg-subtle", emoji: "🔴" },
  error: { label: "Error", dot: "bg-destructive", emoji: "⚠" },
};

const COMPONENT_LABELS: Record<ComponentStatus, string> = {
  ready: "Ready",
  missing: "Missing",
  compiling: "Compiling",
  unavailable: "Unavailable",
  disconnected: "Disconnected",
};

const COMPONENT_DOTS: Record<ComponentStatus, string> = {
  ready: "bg-success",
  missing: "bg-subtle",
  compiling: "bg-warning nc-live-dot",
  unavailable: "bg-destructive",
  disconnected: "bg-subtle",
};

export function BackendStatusBadge() {
  const [open, setOpen] = useState(false);
  const backendHealth = useAppStore((s) => s.backendHealth);
  const config = STATUS_CONFIG[backendHealth.status];
  const system = backendHealth.system;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "flex items-center gap-2 rounded-sm border border-border bg-surface-2 px-2.5 py-1 text-[11px] hover:border-border-strong",
          )}
        >
          <span className="text-[10px]">{config.emoji}</span>
          <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
          <span className="mono text-ivory">{config.label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 border-border bg-popover p-0">
        <div className="hairline-b px-3 py-2">
          <div className="label-caps">System Status</div>
        </div>
        <div className="mono space-y-2 p-3 text-[11px]">
          <Row label="Backend URL" value={backendHealth.url} />
          <Row label="Connection status" value={config.label} />
          <Row label="Last heartbeat" value={backendHealth.lastHeartbeat ?? "—"} />
          <Row label="API version" value={backendHealth.apiVersion ?? "—"} />
        </div>
        {system && (
          <div className="hairline-t px-3 py-2">
            <div className="label-caps mb-2">Components</div>
            <div className="mono space-y-1.5 text-[11px]">
              <ComponentRow label="Workspace" status={system.workspace} />
              <ComponentRow label="Instant-NGP" status={system.instantNgp} />
              <ComponentRow label="Backend" status={system.backend} />
            </div>
          </div>
        )}
        <div className="hairline-t px-3 py-2">
          <div className="label-caps mb-2">API endpoints</div>
          <ul className="mono max-h-32 space-y-1 overflow-y-auto text-[10px] text-muted-foreground">
            {backendHealth.endpoints.map((endpoint) => (
              <li key={endpoint}>{endpoint}</li>
            ))}
          </ul>
        </div>
      </PopoverContent>
    </Popover>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-2">
      <span className="text-subtle">{label}</span>
      <span className="truncate text-ivory">{value}</span>
    </div>
  );
}

function ComponentRow({ label, status }: { label: string; status: ComponentStatus }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-subtle">{label}</span>
      <span className="flex items-center gap-1.5 text-ivory">
        <span className={cn("h-1.5 w-1.5 rounded-full", COMPONENT_DOTS[status])} />
        {COMPONENT_LABELS[status]}
      </span>
    </div>
  );
}
