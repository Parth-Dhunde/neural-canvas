import { createFileRoute, useRouter } from "@tanstack/react-router";
import { PageHeader, Panel, ButtonPro } from "@/components/ui-pro/Panel";
import { EmptyState } from "@/components/ui-pro/EmptyState";
import { StatusBadge } from "@/components/ui-pro/StatusBadge";
import { openExistingJob } from "@/lib/jobActions";
import { formatLoss } from "@/lib/dashboardStats";
import { useAppStore } from "@/store/useAppStore";

export const Route = createFileRoute("/history")({
  component: HistoryPage,
  head: () => ({
    meta: [
      { title: "History — NeuralCanvas" },
      {
        name: "description",
        content: "Timeline of past reconstructions with metrics and downloads.",
      },
    ],
  }),
});

function HistoryPage() {
  const router = useRouter();
  const jobs = useAppStore((s) => s.jobs);
  // Finished runs: completed jobs (newest first), then failed ones (newest created first).
  const finishedJobs = [
    ...jobs
      .filter((j) => j.status === "completed")
      .sort((a, b) => (b.completedAt ?? "").localeCompare(a.completedAt ?? "")),
    ...jobs
      .filter((j) => j.status === "failed")
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt)),
  ];

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow={finishedJobs.length === 0 ? "No history" : `${finishedJobs.length} entries`}
        title="History"
        description="Chronological log of every reconstruction produced in this workspace."
        actions={
          <>
            <ButtonPro variant="outline" reason="Reports are not implemented yet">
              Export report
            </ButtonPro>
            <ButtonPro variant="bronze" reason="Archiving is not implemented yet">
              Archive selected
            </ButtonPro>
          </>
        }
      />

      <div className="p-6">
        <Panel bodyClassName="p-0">
          {finishedJobs.length === 0 ? (
            <EmptyState
              title="No reconstruction history yet."
              description="Completed and failed jobs appear here once the backend is connected and runs finish."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-[12px]">
                <thead>
                  <tr className="hairline-b bg-surface/60 text-left text-[10px] uppercase tracking-widest text-subtle">
                    <th className="px-4 py-2 font-normal">ID</th>
                    <th className="px-4 py-2 font-normal">Name</th>
                    <th className="px-4 py-2 font-normal">Status</th>
                    <th className="px-4 py-2 font-normal">Completed / failure</th>
                    <th className="px-4 py-2 font-normal">Training</th>
                    <th className="px-4 py-2 font-normal">Final loss</th>
                    <th className="px-4 py-2 font-normal">Exports</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {finishedJobs.map((j) => {
                    const exports = Object.entries(j.jobOutputs?.exports ?? {});
                    const loss = j.trainingMetrics?.finalLoss;
                    return (
                      <tr key={j.id} className="hairline-b hover:bg-surface-2/60">
                        <td className="mono px-4 py-2.5 text-bronze">{j.id}</td>
                        <td className="px-4 py-2.5 text-ivory">{j.name}</td>
                        <td className="px-4 py-2.5">
                          <StatusBadge status={j.status} />
                        </td>
                        <td className="mono max-w-[280px] px-4 py-2.5 text-muted-foreground">
                          {j.status === "failed" ? (
                            <span
                              className="block truncate text-destructive"
                              title={j.lastError ?? undefined}
                            >
                              Stage {j.failedStage?.id ?? "?"} ({j.failedStage?.name ?? "unknown"})
                              {j.lastError ? ` · ${j.lastError}` : ""}
                            </span>
                          ) : j.completedAt ? (
                            new Date(j.completedAt).toLocaleString()
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="mono px-4 py-2.5 text-muted-foreground">
                          {j.duration ?? (j.status === "failed" ? "—" : "Not recorded")}
                        </td>
                        <td className="mono px-4 py-2.5 text-muted-foreground">
                          {loss != null ? formatLoss(loss) : "—"}
                        </td>
                        <td className="mono px-4 py-2.5 text-[11px] text-muted-foreground">
                          {exports.length === 0
                            ? "None"
                            : exports
                                .map(([variant, formats]) => `${variant}: ${formats.join("/")}`)
                                .join(" · ")}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          <ButtonPro
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              void openExistingJob(j.id);
                              void router.navigate({ to: "/viewer" });
                            }}
                          >
                            Open in viewer
                          </ButtonPro>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
