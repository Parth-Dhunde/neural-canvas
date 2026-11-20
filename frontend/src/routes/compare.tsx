import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Panel, ButtonPro } from "@/components/ui-pro/Panel";
import { SUPPORTED_ENGINES } from "@/lib/constants";

export const Route = createFileRoute("/compare")({
  component: ComparePage,
  head: () => ({
    meta: [
      { title: "Compare — NeuralCanvas" },
      {
        name: "description",
        content: "Engine comparison (not implemented yet).",
      },
    ],
  }),
});

function ComparePage() {
  const [leftEngine, rightEngine] = SUPPORTED_ENGINES;

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow="Engine comparison"
        title="Compare Engines"
        description="A/B analysis of reconstruction outputs from the same source set."
        actions={
          <>
            <ButtonPro variant="outline" reason="Needs a second reconstruction engine">
              Swap
            </ButtonPro>
            <ButtonPro variant="bronze" reason="Needs a second reconstruction engine">
              Export report
            </ButtonPro>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-4 p-6">
        <PreviewCard side="left" label={leftEngine} />
        <PreviewCard side="right" label={rightEngine} />

        <Panel title="Metric Comparison" className="col-span-2" bodyClassName="p-0">
          <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
            <div className="label-caps mb-2">No comparison data</div>
            <p className="max-w-lg text-[13px] text-muted-foreground">
              Comparison needs a second reconstruction engine. Only Instant-NGP is installed, so
              this page is a preview of a planned feature.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function PreviewCard({ side, label }: { side: "left" | "right"; label: string }) {
  return (
    <Panel
      title={label}
      bodyClassName="p-0"
      action={<span className="mono text-[10px] text-subtle">{side === "left" ? "A" : "B"}</span>}
    >
      <div className="relative aspect-[16/9] w-full overflow-hidden bg-viewport">
        <div className="absolute inset-0 nc-grid opacity-40" />
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <div className="label-caps">No output loaded</div>
          <p className="mono max-w-xs px-4 text-center text-[11px] text-subtle">
            Comparison needs a second reconstruction engine. Only Instant-NGP is installed, so this
            page is a preview of a planned feature.
          </p>
        </div>
        <div className="absolute left-3 top-3 label-caps">
          Preview · {side === "left" ? "A" : "B"}
        </div>
        <div className="absolute right-3 bottom-3 mono rounded-sm border border-border bg-background/70 px-2 py-1 text-[10px] text-muted-foreground backdrop-blur">
          {label}
        </div>
      </div>
    </Panel>
  );
}
