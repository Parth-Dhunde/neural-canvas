import { Cpu, HardDrive, MemoryStick, Thermometer } from "lucide-react";
import { HARDWARE_HELPER_MESSAGE } from "@/lib/constants";
import { useAppStore } from "@/store/useAppStore";

export function HardwarePanel() {
  const hardware = useAppStore((s) => s.hardware);

  return (
    <div className="space-y-3">
      <HardwareRow icon={Cpu} label="Status" value={hardware.status} />
      <HardwareRow icon={Cpu} label="GPU" value={hardware.gpu} />
      <HardwareRow icon={HardDrive} label="Driver" value={hardware.driver} />
      <HardwareRow icon={MemoryStick} label="CUDA" value={hardware.cuda} />
      <HardwareRow icon={MemoryStick} label="Memory" value={hardware.memory} />
      <HardwareRow icon={Thermometer} label="Temperature" value={hardware.temperature} />
      <p className="text-[11px] text-muted-foreground">{HARDWARE_HELPER_MESSAGE}</p>
    </div>
  );
}

function HardwareRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  value: string;
}) {
  return (
    <div className="nc-tile rounded-sm border border-border p-3">
      <div className="flex items-center gap-2.5">
        <Icon className="h-4 w-4 text-bronze" strokeWidth={1.6} />
        <div className="min-w-0 flex-1">
          <div className="label-caps">{label}</div>
          <div className="mono mt-0.5 truncate text-[12px] text-ivory">{value}</div>
        </div>
      </div>
    </div>
  );
}
