import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { PageHeader, ButtonPro } from "@/components/ui-pro/Panel";
import { EmptyState } from "@/components/ui-pro/EmptyState";
import { ThreeViewer } from "@/components/viewer/ThreeViewer";
import { StatusBadge } from "@/components/ui-pro/StatusBadge";
import { getJobImageUrls, getJobPreviewUrls } from "@/services/jobs";
import { getPipeline } from "@/services/pipeline";
import { buildUrl } from "@/services/api";
import { useJobExports } from "@/hooks/useJobExports";
import {
  downloadLinks,
  effectiveViewerTab,
  selectViewerMesh,
  viewerJobs,
} from "@/lib/meshSelection";
import { useAppStore } from "@/store/useAppStore";
import type { PipelineStep, ViewerImageSource } from "@/types";
import { cn } from "@/lib/utils";
import { Layers, Sun, Aperture, Ruler } from "lucide-react";

export const Route = createFileRoute("/viewer")({
  component: ViewerPage,
  head: () => ({
    meta: [
      { title: "Viewer — NeuralCanvas" },
      {
        name: "description",
        content: "Inspect reconstructed meshes and their source images.",
      },
    ],
  }),
});

function ViewerPage() {
  const jobs = useAppStore((s) => s.jobs);
  const viewer = useAppStore((s) => s.viewer);
  const settings = useAppStore((s) => s.settings);
  const setViewer = useAppStore((s) => s.setViewer);
  const [jobPipeline, setJobPipeline] = useState<PipelineStep[]>([]);
  const backgroundRemovalDone = jobPipeline.find((step) => step.id === 2)?.status === "completed";
  const listedJobs = viewerJobs(jobs);
  const selectedJob =
    listedJobs.find((j) => j.id === viewer.selectedJobId) ?? listedJobs[0] ?? null;
  const tab = effectiveViewerTab(selectedJob, viewer.imageSource);
  const imageSource = tab;
  const displayUrls =
    selectedJob && tab !== "model"
      ? tab === "masked"
        ? getJobImageUrls(selectedJob, settings.backendUrl, "masked")
        : getJobPreviewUrls(selectedJob, settings.backendUrl)
      : [];
  const exportsState = useJobExports(selectedJob?.id ?? null);
  const viewerMesh = selectViewerMesh(exportsState.manifest);
  const links = downloadLinks(exportsState.manifest, viewerMesh?.variant ?? null);
  const originalLinks = downloadLinks(exportsState.manifest, "original");
  const hasImages = (selectedJob?.imageCount ?? 0) > 0;
  const hasMesh = Boolean(selectedJob?.meshPath);
  const tabs: { id: ViewerImageSource; label: string; enabled: boolean }[] = [
    { id: "model", label: "3D Model", enabled: hasMesh },
    { id: "original", label: "Original Images", enabled: hasImages },
    { id: "masked", label: "Masked Images", enabled: hasImages && backgroundRemovalDone },
  ];

  // Keyed on the id, not the job object: job polling replaces the object on every refresh,
  // and the pipeline only needs refetching when a different job is selected.
  const selectedJobId = selectedJob?.id ?? null;
  useEffect(() => {
    if (!selectedJobId) {
      setJobPipeline([]);
      return;
    }
    let active = true;
    void getPipeline(selectedJobId, settings.backendUrl).then((steps) => {
      if (active) setJobPipeline(steps);
    });
    return () => {
      active = false;
    };
  }, [selectedJobId, settings.backendUrl]);

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Model & imagery"
        title="Viewer"
        description="Inspect reconstructed meshes and the source imagery behind them."
        actions={
          <>
            <ButtonPro variant="outline" reason="Viewport snapshots are not implemented yet">
              Snapshot
            </ButtonPro>
            {links.glb ? (
              <a
                href={buildUrl(links.glb, settings.backendUrl)}
                download
                className="inline-flex h-8 items-center gap-1.5 rounded-sm border border-bronze/60 bg-bronze/12 px-3 text-[12px] font-medium uppercase tracking-wider text-bronze transition-colors hover:bg-bronze/20"
              >
                Export mesh
              </a>
            ) : (
              <ButtonPro variant="bronze" disabled>
                Export mesh
              </ButtonPro>
            )}
          </>
        }
      />

      <div className="grid min-h-0 flex-1 grid-cols-[260px_1fr_300px] gap-0">
        <div className="hairline-r flex flex-col bg-surface/40">
          <div className="hairline-b nc-panel-header px-4 py-3">
            <div className="label-caps">Jobs · {listedJobs.length}</div>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {listedJobs.length === 0 ? (
              <EmptyState
                title="Nothing to view yet"
                description="Upload images or generate a mesh for a job to view it here."
                className="py-8"
              />
            ) : (
              listedJobs.map((j) => (
                <button
                  key={j.id}
                  onClick={() =>
                    setViewer({
                      selectedJobId: j.id,
                      displayState: "empty",
                    })
                  }
                  className={cn(
                    "mb-1 flex w-full items-center gap-3 rounded-sm border p-2 text-left transition-colors",
                    selectedJob?.id === j.id
                      ? "border-selected/45 bg-selected/8"
                      : "border-transparent hover:bg-surface-2",
                  )}
                >
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-sm border border-border bg-surface-3">
                    <span className="mono text-[10px] text-bronze">{j.imageCount ?? 0}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="mono truncate text-[11px] text-ivory">{j.id}</div>
                    <div className="truncate text-[11px] text-muted-foreground">{j.name}</div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        <div className="flex min-w-0 flex-col bg-viewport">
          <div className="hairline-b nc-panel-header flex h-9 shrink-0 items-center justify-between gap-3 bg-surface/60 px-3">
            <div className="mono truncate text-[10px] uppercase tracking-widest text-subtle">
              {selectedJob
                ? `${selectedJob.id} · ${selectedJob.imageCount ?? 0} images${hasMesh ? " · mesh" : ""}`
                : "No job selected"}
            </div>
            <div
              role="tablist"
              aria-label="Viewer content"
              className="flex items-center gap-1 rounded-sm border border-border bg-surface-2 p-0.5"
            >
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setViewer({ imageSource: t.id })}
                  disabled={!t.enabled}
                  className={cn(
                    "mono rounded-sm px-2 py-0.5 text-[10px] uppercase tracking-widest transition-colors",
                    tab === t.id
                      ? "bg-selected/15 text-selected"
                      : "text-muted-foreground hover:text-ivory",
                    !t.enabled && "cursor-not-allowed opacity-50",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div className="relative min-h-0 flex-1">
            {tab === "model" ? (
              <ThreeViewer
                className="absolute inset-0"
                jobId={selectedJob?.id ?? null}
                jobLabel={selectedJob ? `${selectedJob.id} · ${selectedJob.name}` : undefined}
                manifest={exportsState.manifest}
                manifestStatus={exportsState.status}
                manifestError={exportsState.error}
                onRetry={exportsState.reload}
              />
            ) : selectedJob && displayUrls.length > 0 ? (
              <div className="absolute inset-0 flex flex-col">
                <div className="flex-1 overflow-y-auto p-4">
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
                    {displayUrls.map((url, index) => (
                      <div
                        key={url}
                        className="overflow-hidden rounded-sm border border-border bg-surface-3"
                      >
                        <img
                          src={url}
                          alt={selectedJob.imageFilenames?.[index] ?? `Image ${index + 1}`}
                          className={cn(
                            "aspect-square w-full object-cover",
                            imageSource === "masked" &&
                              "bg-[repeating-conic-gradient(var(--surface-3)_0%_25%,var(--surface-2)_0%_50%)] bg-[length:16px_16px]",
                          )}
                        />
                        <div className="mono truncate px-2 py-1 text-[10px] text-muted-foreground">
                          {selectedJob.imageFilenames?.[index] ?? `Image ${index + 1}`}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState
                title="No images"
                description="This job has no uploaded images."
                className="py-8"
              />
            )}
          </div>
        </div>

        <div className="hairline-l flex flex-col overflow-y-auto bg-surface/40">
          <div className="hairline-b nc-panel-header px-4 py-3">
            <div className="label-caps">Inspector</div>
            {selectedJob ? (
              <>
                <div className="mono mt-1 text-[13px] text-ivory">{selectedJob.name}</div>
                <StatusBadge status={selectedJob.status} className="mt-2" />
              </>
            ) : (
              <div className="mono mt-1 text-[13px] text-muted-foreground">No selection</div>
            )}
          </div>

          {!selectedJob ? (
            <EmptyState
              title="No model loaded"
              description="Upload images and complete a reconstruction to preview a mesh."
              className="py-8"
            />
          ) : (
            <>
              <Section title="Mesh" icon={Layers}>
                <Kv k="Default mesh" v={viewerMesh ? viewerMesh.variant : "—"} />
                <Kv k="Cleanup" v={selectedJob.meshCleanupStatus ?? "not run"} />
                <Kv
                  k="Stage 5 size"
                  v={
                    selectedJob.triangleCount
                      ? `${selectedJob.vertexCount?.toLocaleString()} v · ${selectedJob.triangleCount.toLocaleString()} f`
                      : "—"
                  }
                />
              </Section>

              <Section title="Source Images" icon={Layers}>
                <Kv k="Count" v={String(selectedJob.imageCount ?? 0)} />
                <Kv k="Uploaded" v={selectedJob.uploadedAt ?? "—"} />
              </Section>

              <Section title="Materials" icon={Sun}>
                <Kv k="Base Color" v="—" />
                <Kv k="Roughness" v="—" />
                <Kv k="Metalness" v="—" />
                <Kv k="Textures" v="—" />
              </Section>

              <Section title="Reconstruction" icon={Aperture}>
                <Kv k="Engine" v={selectedJob.engine} />
                <Kv k="Source Images" v={String(selectedJob.imageCount ?? 0)} />
                <Kv
                  k="Iterations"
                  v={
                    selectedJob.trainingMetrics?.totalSteps != null
                      ? selectedJob.trainingMetrics.totalSteps.toLocaleString("en-US")
                      : "N/A"
                  }
                />
                <Kv
                  k="PSNR"
                  v={
                    selectedJob.psnrDb != null
                      ? `${selectedJob.psnrDb.toFixed(2)} dB`
                      : "Not evaluated"
                  }
                />
                <Kv k="Training Time" v={selectedJob.duration ?? "N/A"} />
              </Section>

              <Section title="Export" icon={Ruler}>
                <div className="mb-2 text-[11px] text-muted-foreground">
                  {viewerMesh
                    ? viewerMesh.variant === "cleaned"
                      ? "Cleaned mesh (Stage 6)."
                      : `Original Stage 5 mesh${
                          exportsState.manifest?.variants.cleaned.unavailable_reason
                            ? ` — ${exportsState.manifest.variants.cleaned.unavailable_reason}`
                            : ""
                        }.`
                    : exportsState.status === "loading"
                      ? "Checking exports…"
                      : "No mesh available yet."}
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {(["glb", "obj", "ply"] as const).map((fmt) =>
                    links[fmt] ? (
                      <a
                        key={fmt}
                        href={buildUrl(links[fmt]!, settings.backendUrl)}
                        download
                        className="mono grid h-7 place-items-center rounded-sm border border-border bg-surface-2 text-[11px] uppercase text-ivory hover:border-border-strong hover:bg-surface-3"
                      >
                        {fmt}
                      </a>
                    ) : (
                      <button
                        key={fmt}
                        disabled
                        className="mono h-7 rounded-sm border border-border bg-surface-2 text-[11px] uppercase text-muted-foreground opacity-50"
                      >
                        {fmt}
                      </button>
                    ),
                  )}
                  {["FBX", "USDZ", "STL"].map((f) => (
                    <button
                      key={f}
                      disabled
                      title="Not supported yet"
                      className="mono h-7 rounded-sm border border-border bg-surface-2 text-[11px] text-muted-foreground opacity-50"
                    >
                      {f}
                    </button>
                  ))}
                </div>
                {viewerMesh?.variant === "cleaned" && Object.keys(originalLinks).length > 0 && (
                  <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                    Original:
                    {(["glb", "obj", "ply"] as const).map((fmt) =>
                      originalLinks[fmt] ? (
                        <a
                          key={fmt}
                          href={buildUrl(originalLinks[fmt]!, settings.backendUrl)}
                          download
                          className="mono uppercase text-bronze hover:underline"
                        >
                          {fmt}
                        </a>
                      ) : null,
                    )}
                  </div>
                )}
              </Section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  children: React.ReactNode;
}) {
  return (
    <div className="hairline-b px-4 py-3">
      <div className="mb-2 flex items-center gap-2 label-caps">
        <Icon className="h-3 w-3 text-bronze" strokeWidth={1.6} />
        {title}
      </div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function Kv({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="text-subtle">{k}</span>
      <span className="mono text-ivory">{v}</span>
    </div>
  );
}
