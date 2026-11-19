import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Panel, ButtonPro } from "@/components/ui-pro/Panel";
import { HardwarePanel } from "@/components/ui-pro/HardwarePanel";
import { useHardwareTelemetry } from "@/hooks/useHardwareTelemetry";
import { APP_NAME, APP_SUBTITLE, SUPPORTED_ENGINES } from "@/lib/constants";
import { useAppStore } from "@/store/useAppStore";
import { useTheme } from "@/hooks/useTheme";
import type { ThemePreference } from "@/lib/theme";
import { useState } from "react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
  head: () => ({
    meta: [
      { title: "Settings — NeuralCanvas" },
      {
        name: "description",
        content:
          "Configure default engine, mesh quality, export format, and application preferences.",
      },
    ],
  }),
});

const sections = ["Reconstruction", "Performance", "Export", "Interface", "About"] as const;

function SettingsPage() {
  useHardwareTelemetry(true);
  const [active, setActive] = useState<(typeof sections)[number]>("Reconstruction");
  const settings = useAppStore((s) => s.settings);
  const setSettings = useAppStore((s) => s.setSettings);
  const theme = useTheme();

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Preferences"
        title="Settings"
        description="Backend URL and theme apply immediately. Reconstruction, mesh and export parameters are configured on the backend (backend/.env); rows marked “Not connected” are shown for reference only."
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 md:grid-cols-[220px_1fr]">
        <nav className="hairline-b md:hairline-r flex gap-1 overflow-x-auto bg-surface/40 p-3 md:block md:border-b-0">
          {sections.map((s) => (
            <button
              key={s}
              onClick={() => setActive(s)}
              className={cn(
                "flex shrink-0 items-center rounded-sm px-2.5 py-2 text-[12px] whitespace-nowrap transition-colors md:w-full",
                active === s
                  ? "bg-selected/10 text-ivory"
                  : "text-muted-foreground hover:bg-surface-2",
              )}
            >
              <span
                className={cn(
                  "mr-2 h-1 w-1 rounded-full",
                  active === s ? "bg-selected" : "bg-subtle",
                )}
              />
              {s}
            </button>
          ))}
        </nav>

        <div className="space-y-4 overflow-y-auto p-4 sm:p-6">
          {active === "Reconstruction" && (
            <>
              <SettingRow
                label="Default engine"
                hint="Applied when creating new reconstruction jobs."
                unavailable="Instant-NGP is the only engine"
              >
                <Segmented
                  value={settings.defaultEngine}
                  onChange={(v) =>
                    setSettings({
                      defaultEngine: v as (typeof SUPPORTED_ENGINES)[number],
                    })
                  }
                  options={[...SUPPORTED_ENGINES]}
                />
              </SettingRow>

              <SettingRow
                label="Mesh quality"
                unavailable="Set in backend/.env (MESH_RESOLUTION)"
                hint={`Current preset: ${qualityLabel(settings.meshQuality)}`}
              >
                <div className="flex w-full max-w-96 items-center gap-3">
                  <input
                    type="range"
                    min={10}
                    max={100}
                    value={settings.meshQuality}
                    onChange={(e) => setSettings({ meshQuality: parseInt(e.target.value) })}
                    className="flex-1 accent-bronze"
                  />
                  <span className="mono w-10 text-right text-[12px] text-ivory">
                    {settings.meshQuality}
                  </span>
                </div>
              </SettingRow>

              <SettingRow
                label="Background removal"
                hint="Automatic segmentation before training."
                unavailable="Always runs as Stage 2"
              >
                <Toggle
                  on={settings.backgroundRemoval}
                  onChange={(v) => setSettings({ backgroundRemoval: v })}
                />
              </SettingRow>

              <SettingRow
                label="Auto camera estimation"
                hint="COLMAP structure-from-motion pass."
                unavailable="Always runs as Stage 3"
              >
                <Toggle
                  on={settings.autoCameraEstimation}
                  onChange={(v) => setSettings({ autoCameraEstimation: v })}
                />
              </SettingRow>

              <SettingRow
                label="Mesh cleanup"
                unavailable="Always runs as Stage 6 (Set in backend/.env)"
                hint="Remove floating islands and non-manifold geometry."
              >
                <Toggle
                  on={settings.meshCleanup}
                  onChange={(v) => setSettings({ meshCleanup: v })}
                />
              </SettingRow>
            </>
          )}

          {active === "Performance" && (
            <>
              <SettingRow label="Backend URL" hint="FastAPI reconstruction server endpoint.">
                <input
                  value={settings.backendUrl}
                  onChange={(e) => setSettings({ backendUrl: e.target.value })}
                  className="mono h-8 w-72 rounded-sm border border-border bg-surface-2 px-2 text-[12px] text-ivory"
                />
              </SettingRow>
              <SettingRow
                label="Precision"
                hint="Trade-off between speed and numerical accuracy."
                unavailable="Not implemented yet"
              >
                <Segmented
                  value={settings.precision}
                  onChange={(v) => setSettings({ precision: v })}
                  options={["FP32", "FP16 mixed", "BF16"]}
                />
              </SettingRow>
              <SettingRow
                label="Ray batch size"
                unavailable="Not implemented yet"
                hint="Lower this if you encounter out-of-memory errors."
              >
                <input
                  value={settings.rayBatchSize}
                  onChange={(e) => setSettings({ rayBatchSize: parseInt(e.target.value) || 4096 })}
                  type="number"
                  className="mono h-8 w-32 rounded-sm border border-border bg-surface-2 px-2 text-[12px] text-ivory"
                />
              </SettingRow>
              <SettingRow
                label="Persistent cache"
                unavailable="Not implemented yet"
                hint="Reuse hash-grid checkpoints between similar jobs."
              >
                <Toggle defaultOn />
              </SettingRow>
              <SettingRow
                label="Telemetry"
                hint="Send anonymous performance diagnostics."
                unavailable="No telemetry is collected"
              >
                <Toggle />
              </SettingRow>
            </>
          )}

          {active === "Export" && (
            <>
              <SettingRow label="Default format" unavailable="GLB, OBJ and PLY are all exported">
                <Segmented
                  value={settings.exportFormat}
                  onChange={(v) => setSettings({ exportFormat: v })}
                  options={["GLB", "OBJ", "PLY", "USDZ", "FBX", "STL"]}
                />
              </SettingRow>
              <SettingRow
                label="Texture resolution"
                unavailable="Meshes use vertex colours; no textures"
              >
                <Segmented value="4K" onChange={() => {}} options={["1K", "2K", "4K", "8K"]} />
              </SettingRow>
              <SettingRow
                label="Embed materials"
                hint="Bake PBR materials into the output file."
                unavailable="Meshes use vertex colours; no materials"
              >
                <Toggle defaultOn />
              </SettingRow>
              <SettingRow
                label="Coordinate system"
                unavailable="Exports keep the reconstruction frame"
              >
                <Segmented value="Y-Up" onChange={() => {}} options={["Y-Up", "Z-Up"]} />
              </SettingRow>
            </>
          )}

          {active === "Interface" && (
            <>
              <SettingRow
                label="Theme"
                hint={`Saved in this browser. System follows your OS setting (currently ${theme.resolved}).`}
              >
                <Segmented
                  value={theme.ready ? THEME_LABELS[theme.preference] : ""}
                  onChange={(label) => theme.setPreference(themeFromLabel(label))}
                  options={Object.values(THEME_LABELS)}
                />
              </SettingRow>
              <SettingRow
                label="Dense tables"
                hint="Reduce row height on the Jobs table."
                unavailable="Not implemented yet"
              >
                <Toggle
                  on={settings.denseTables}
                  onChange={(v) => setSettings({ denseTables: v })}
                />
              </SettingRow>
              <SettingRow
                label="Terminal on launch"
                unavailable="Not implemented yet"
                hint="Open the integrated terminal by default."
              >
                <Toggle
                  on={settings.terminalOnLaunch}
                  onChange={(v) => setSettings({ terminalOnLaunch: v })}
                />
              </SettingRow>
              <SettingRow label="Keyboard shortcuts" unavailable="Not implemented yet">
                <ButtonPro variant="outline" size="sm">
                  View reference
                </ButtonPro>
              </SettingRow>
            </>
          )}

          {active === "About" && (
            <>
              <Panel title="Application">
                <div className="mono grid grid-cols-[160px_1fr] gap-y-2 text-[12px]">
                  <span className="text-subtle">Product</span>
                  <span className="text-ivory">{APP_NAME}</span>
                  <span className="text-subtle">Version</span>
                  <span className="text-ivory">0.1.0 (development)</span>
                  <span className="text-subtle">Engines</span>
                  <span className="text-ivory">{SUPPORTED_ENGINES.join(" · ")}</span>
                  <span className="text-subtle">Backend</span>
                  <span className="text-ivory">FastAPI · {settings.backendUrl}</span>
                </div>
                <p className="mt-4 text-[12px] text-muted-foreground">
                  {APP_NAME} is {APP_SUBTITLE.toLowerCase()}. Ingest, train, mesh, and export in one
                  workflow.
                </p>
              </Panel>
              <Panel title="Hardware">
                <HardwarePanel />
              </Panel>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const THEME_LABELS: Record<ThemePreference, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

function themeFromLabel(label: string): ThemePreference {
  const match = (Object.keys(THEME_LABELS) as ThemePreference[]).find(
    (key) => THEME_LABELS[key] === label,
  );
  return match ?? "dark";
}

function qualityLabel(q: number) {
  if (q < 30) return "Draft";
  if (q < 55) return "Preview";
  if (q < 80) return "Production";
  return "Master";
}

function SettingRow({
  label,
  hint,
  unavailable,
  children,
}: {
  label: string;
  hint?: string;
  /** Reason the control has no effect; the control is shown disabled for reference. */
  unavailable?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 items-start gap-3 rounded-sm border border-border bg-surface-2/60 p-4 md:grid-cols-[280px_1fr] md:gap-6">
      <div>
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-ivory">
          {label}
          {unavailable && (
            <span className="rounded-sm border border-border-strong px-1.5 py-px text-[9px] tracking-widest text-subtle uppercase">
              Not connected
            </span>
          )}
        </div>
        {hint && <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>}
        {unavailable && <div className="mt-1 text-[11px] text-subtle">{unavailable}</div>}
      </div>
      {/* A disabled fieldset disables every control inside it. */}
      <fieldset
        disabled={Boolean(unavailable)}
        className={cn("flex min-w-0 flex-wrap items-center", unavailable && "opacity-50")}
      >
        {children}
      </fieldset>
    </div>
  );
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-0.5 rounded-sm border border-border bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          aria-pressed={value === o}
          className={cn(
            "mono px-3 py-1 text-[11px] rounded-sm transition-colors disabled:cursor-not-allowed",
            value === o
              ? "bg-surface text-selected shadow-sm ring-1 ring-selected/45"
              : "text-muted-foreground hover:text-ivory",
          )}
        >
          {o}
        </button>
      ))}
    </div>
  );
}

function Toggle({
  on: controlledOn,
  onChange,
  defaultOn,
}: {
  on?: boolean;
  onChange?: (v: boolean) => void;
  defaultOn?: boolean;
}) {
  const [internal, setInternal] = useState(!!defaultOn);
  const on = controlledOn ?? internal;
  const toggle = () => {
    const next = !on;
    setInternal(next);
    onChange?.(next);
  };
  return (
    <button
      onClick={toggle}
      className={cn(
        "relative h-5 w-9 rounded-full border transition-colors",
        on ? "border-selected/60 bg-selected/30" : "border-border bg-surface-3",
      )}
    >
      <span
        className={cn(
          "absolute top-0.5 h-3.5 w-3.5 rounded-full transition-all",
          on ? "left-[18px] bg-selected" : "left-0.5 bg-muted-foreground",
        )}
      />
    </button>
  );
}
