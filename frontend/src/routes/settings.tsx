import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PageHeader, Panel, ButtonPro } from "@/components/ui-pro/Panel";
import { HardwarePanel } from "@/components/ui-pro/HardwarePanel";
import { WipBadge } from "@/components/ui-pro/WipBadge";
import { useHardwareTelemetry } from "@/hooks/useHardwareTelemetry";
import { APP_DESCRIPTION, APP_NAME, DEFAULT_BACKEND_URL, SUPPORTED_ENGINES } from "@/lib/constants";
import { ENGINE_OPTIONS, isSubmittableEngine } from "@/lib/engines";
import { normalizeBackendUrl } from "@/lib/settingsStorage";
import { pingHealth } from "@/services/health";
import { getPipelineConfig, type PipelineConfigApi } from "@/services/system";
import { useAppStore } from "@/store/useAppStore";
import { useTheme } from "@/hooks/useTheme";
import type { ThemePreference } from "@/lib/theme";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/settings")({
  component: SettingsPage,
  head: () => ({
    meta: [
      { title: "Settings — NeuralCanvas" },
      {
        name: "description",
        content:
          "Backend connection, default engine, interface preferences and pipeline parameters.",
      },
    ],
  }),
});

const sections = ["Connection", "Reconstruction", "Interface", "About"] as const;

function SettingsPage() {
  useHardwareTelemetry(true);
  const [active, setActive] = useState<(typeof sections)[number]>("Connection");
  const settings = useAppStore((s) => s.settings);
  const setSettings = useAppStore((s) => s.setSettings);
  const setSelectedEngine = useAppStore((s) => s.setSelectedEngine);
  const theme = useTheme();

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Preferences"
        title="Settings"
        description="Changes apply immediately and are saved in this browser. Reconstruction parameters are configured on the backend and shown here read-only."
      />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 md:grid-cols-[220px_1fr]">
        <nav className="hairline-b md:hairline-r flex gap-1 overflow-x-auto bg-surface/40 p-3 md:block md:border-b-0">
          {sections.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setActive(s)}
              aria-current={active === s ? "page" : undefined}
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
          {active === "Connection" && <ConnectionSection />}

          {active === "Reconstruction" && (
            <>
              <SettingRow
                label="Default engine"
                hint="Selected when the app loads and used for new jobs. Work-in-progress engines cannot be selected."
              >
                <div className="flex flex-wrap items-center gap-0.5 rounded-sm border border-border bg-surface-2 p-0.5">
                  {ENGINE_OPTIONS.map((option) => {
                    const available = isSubmittableEngine(option.id);
                    return (
                      <button
                        key={option.id}
                        type="button"
                        disabled={!available}
                        title={option.description}
                        aria-pressed={settings.defaultEngine === option.id}
                        onClick={() => {
                          if (!isSubmittableEngine(option.id)) return;
                          setSettings({ defaultEngine: option.id });
                          setSelectedEngine(option.id);
                        }}
                        className={cn(
                          "mono flex items-center gap-2 rounded-sm px-3 py-1 text-[11px] transition-colors disabled:cursor-not-allowed disabled:text-subtle",
                          settings.defaultEngine === option.id
                            ? "bg-surface text-selected shadow-sm ring-1 ring-selected/45"
                            : "text-muted-foreground hover:text-ivory",
                        )}
                      >
                        {option.id}
                        {!available && <WipBadge />}
                      </button>
                    );
                  })}
                </div>
              </SettingRow>
              <PipelineConfigPanel />
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
              <SettingRow label="Dense tables" hint="Compact rows on the Jobs table.">
                <Toggle
                  label="Dense tables"
                  on={settings.denseTables}
                  onChange={(v) => setSettings({ denseTables: v })}
                />
              </SettingRow>
              <SettingRow
                label="Terminal on launch"
                hint="Open the integrated terminal when the app loads. Takes effect on the next load."
              >
                <Toggle
                  label="Terminal on launch"
                  on={settings.terminalOnLaunch}
                  onChange={(v) => setSettings({ terminalOnLaunch: v })}
                />
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
                  <span className="text-ivory">
                    {SUPPORTED_ENGINES.join(" · ")} · Text-to-3D (work in progress)
                  </span>
                  <span className="text-subtle">Backend</span>
                  <span className="text-ivory">FastAPI · {settings.backendUrl}</span>
                </div>
                <p className="mt-4 text-[12px] text-muted-foreground">{APP_DESCRIPTION}</p>
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

function ConnectionSection() {
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const status = useAppStore((s) => s.backendHealth.status);
  const setSettings = useAppStore((s) => s.setSettings);
  const [draft, setDraft] = useState(backendUrl);
  const [error, setError] = useState<string | null>(null);
  const [test, setTest] = useState<{ state: "idle" | "testing" | "ok" | "failed"; url?: string }>({
    state: "idle",
  });

  useEffect(() => setDraft(backendUrl), [backendUrl]);

  const save = (value: string) => {
    const normalized = normalizeBackendUrl(value);
    if (!normalized) {
      setError("Enter an http:// or https:// URL, e.g. http://localhost:8000");
      return;
    }
    setError(null);
    setSettings({ backendUrl: normalized });
  };

  const runTest = async () => {
    const normalized = normalizeBackendUrl(draft);
    if (!normalized) {
      setError("Enter an http:// or https:// URL, e.g. http://localhost:8000");
      return;
    }
    setError(null);
    setTest({ state: "testing", url: normalized });
    const ok = await pingHealth(normalized);
    setTest({ state: ok ? "ok" : "failed", url: normalized });
  };

  const statusLabel =
    status === "connected" ? "Connected" : status === "connecting" ? "Checking" : "Disconnected";

  return (
    <SettingRow
      label="Backend URL"
      hint={`FastAPI reconstruction server. Current status: ${statusLabel}. Saved URLs are checked automatically.`}
    >
      <form
        className="flex w-full flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          save(draft);
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setTest({ state: "idle" });
            }}
            aria-label="Backend URL"
            aria-invalid={Boolean(error)}
            className="mono h-8 w-72 max-w-full rounded-sm border border-border bg-surface-2 px-2 text-[12px] text-ivory"
          />
          <ButtonPro
            type="submit"
            size="sm"
            variant="bronze"
            disabled={draft.trim() === backendUrl}
          >
            Save
          </ButtonPro>
          <ButtonPro
            size="sm"
            variant="outline"
            loading={test.state === "testing"}
            onClick={() => void runTest()}
          >
            Test connection
          </ButtonPro>
          <ButtonPro
            size="sm"
            variant="ghost"
            disabled={backendUrl === DEFAULT_BACKEND_URL && draft === DEFAULT_BACKEND_URL}
            onClick={() => {
              setDraft(DEFAULT_BACKEND_URL);
              save(DEFAULT_BACKEND_URL);
            }}
          >
            Reset to default
          </ButtonPro>
        </div>
        {error && <p className="text-[11px] text-destructive">{error}</p>}
        {test.state === "ok" && (
          <p className="text-[11px] text-success">{test.url} answered /health.</p>
        )}
        {test.state === "failed" && (
          <p className="text-[11px] text-destructive">{test.url} did not answer /health.</p>
        )}
      </form>
    </SettingRow>
  );
}

function PipelineConfigPanel() {
  const backendUrl = useAppStore((s) => s.settings.backendUrl);
  const status = useAppStore((s) => s.backendHealth.status);
  const [config, setConfig] = useState<PipelineConfigApi | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "connected") return;
    let active = true;
    getPipelineConfig(backendUrl)
      .then((value) => {
        if (active) {
          setConfig(value);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (active) setError(e instanceof Error ? e.message : "Could not load the configuration");
      });
    return () => {
      active = false;
    };
  }, [backendUrl, status]);

  const rows: [string, string][] = config
    ? [
        ["Stages (always run, in order)", config.stages_always_run.join(" → ")],
        ["Camera model (COLMAP)", config.camera_estimation.camera_model],
        ["COLMAP GPU", config.camera_estimation.use_gpu ? "On" : "Off"],
        [
          "Minimum registered images",
          `${Math.round(config.camera_estimation.min_registration_ratio * 100)}%`,
        ],
        ["Training steps (Instant-NGP)", String(config.training.n_steps)],
        ["Mesh resolution", String(config.mesh.resolution)],
        ["Mesh density threshold", String(config.mesh.density_threshold)],
        ["Cleanup smoothing iterations", String(config.mesh_cleanup.taubin_iterations)],
        ["Cleanup: remove pieces under", `${config.mesh_cleanup.min_component_faces} faces`],
        [
          "Cleanup: decimation range",
          `${config.mesh_cleanup.decimate_min_faces.toLocaleString()}–${config.mesh_cleanup.decimate_max_faces.toLocaleString()} faces`,
        ],
        [
          "Export formats (all produced)",
          config.export_formats.map((f) => f.toUpperCase()).join(", "),
        ],
      ]
    : [];

  return (
    <Panel title="Pipeline parameters · read-only">
      <p className="mb-3 text-[12px] text-muted-foreground">
        These values are set on the backend (<span className="mono">backend/.env</span>) and apply
        to every job. They can&apos;t be changed from the browser, because the pipeline reads them
        when the backend starts.
      </p>
      {status !== "connected" ? (
        <p className="text-[12px] text-subtle">
          Connect the backend to view its current parameters.
        </p>
      ) : error ? (
        <p className="text-[12px] text-destructive">{error}</p>
      ) : !config ? (
        <p className="text-[12px] text-subtle">Loading…</p>
      ) : (
        <dl className="mono grid grid-cols-1 gap-x-6 gap-y-1.5 text-[12px] sm:grid-cols-[240px_1fr]">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-subtle">{k}</dt>
              <dd className="text-ivory">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </Panel>
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

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 items-start gap-3 rounded-sm border border-border bg-surface-2/60 p-4 md:grid-cols-[280px_1fr] md:gap-6">
      <div>
        <div className="text-[13px] text-ivory">{label}</div>
        {hint && <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>}
      </div>
      <div className="flex min-w-0 flex-wrap items-center">{children}</div>
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
          type="button"
          onClick={() => onChange(o)}
          aria-pressed={value === o}
          className={cn(
            "mono rounded-sm px-3 py-1 text-[11px] transition-colors",
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
  on,
  onChange,
  label,
}: {
  on: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
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
