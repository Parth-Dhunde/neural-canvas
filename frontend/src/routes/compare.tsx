import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Panel } from "@/components/ui-pro/Panel";
import { WipBadge } from "@/components/ui-pro/WipBadge";
import { ENGINE_OPTIONS } from "@/lib/engines";

export const Route = createFileRoute("/compare")({
  component: ComparePage,
  head: () => ({
    meta: [
      { title: "Compare — NeuralCanvas" },
      { name: "description", content: "Engine comparison (work in progress)." },
    ],
  }),
});

const EXPLANATION =
  "Comparison needs two engines that can both produce results. Only Instant-NGP is available; Text-to-3D is a work in progress, so there is nothing to compare yet.";

function ComparePage() {
  const [left, right] = ENGINE_OPTIONS;

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Engine comparison · work in progress"
        title="Compare Engines"
        description="A/B analysis of reconstruction outputs from the same source set. This page is a preview of a planned feature and has no controls yet."
        actions={<WipBadge label="Coming soon" />}
      />

      <div className="grid grid-cols-1 gap-4 p-4 sm:p-6 lg:grid-cols-2">
        <PreviewCard side="A" engine={left.id} available={left.availability === "available"} />
        <PreviewCard side="B" engine={right.id} available={right.availability === "available"} />

        <Panel title="Metric Comparison" className="lg:col-span-2" bodyClassName="p-0">
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <div className="mb-2 flex items-center gap-2">
              <span className="label-caps">No comparison data</span>
              <WipBadge />
            </div>
            <p className="max-w-lg text-[13px] text-muted-foreground">{EXPLANATION}</p>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function PreviewCard({
  side,
  engine,
  available,
}: {
  side: "A" | "B";
  engine: string;
  available: boolean;
}) {
  return (
    <Panel
      title={engine}
      bodyClassName="p-0"
      action={
        available ? (
          <span className="mono text-[10px] text-success">AVAILABLE · {side}</span>
        ) : (
          <WipBadge />
        )
      }
    >
      <div className="relative aspect-[16/9] w-full overflow-hidden bg-viewport">
        <div className="absolute inset-0 nc-grid opacity-40" />
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <div className="label-caps">No output loaded</div>
          <p className="mono max-w-xs px-4 text-center text-[11px] text-subtle">
            {available
              ? "Results from this engine appear here once comparison is implemented."
              : `${engine} is not available yet.`}
          </p>
        </div>
        <div className="absolute left-3 top-3 label-caps">Preview · {side}</div>
      </div>
    </Panel>
  );
}
