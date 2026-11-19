import { createFileRoute, useRouter } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Search, Filter, ArrowUpDown, Play, Pause, Trash2, Download } from "lucide-react";
import { PageHeader, Panel, ButtonPro } from "@/components/ui-pro/Panel";
import { EmptyState } from "@/components/ui-pro/EmptyState";
import { StatusBadge } from "@/components/ui-pro/StatusBadge";
import { ProgressBar } from "@/components/ui-pro/ProgressBar";
import { SUPPORTED_ENGINES } from "@/lib/constants";
import { createNewJob, openExistingJob } from "@/lib/jobActions";
import { useAppStore } from "@/store/useAppStore";
import type { JobStatus } from "@/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/jobs")({
  component: JobsPage,
  head: () => ({
    meta: [
      { title: "Jobs — NeuralCanvas" },
      { name: "description", content: "Manage active, queued, and completed reconstruction jobs." },
    ],
  }),
});

const statuses: (JobStatus | "all")[] = [
  "all",
  "waiting",
  "running",
  "queued",
  "completed",
  "failed",
  "paused",
];
const engineFilters = ["All engines", ...SUPPORTED_ENGINES];

function JobsPage() {
  const router = useRouter();
  const jobs = useAppStore((s) => s.jobs);
  const [status, setStatus] = useState<(typeof statuses)[number]>("all");
  const [engine, setEngine] = useState(engineFilters[0]);
  const [query, setQuery] = useState("");
  const [sortBy, setSortBy] = useState<"createdAt" | "duration" | "progress">("createdAt");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    return jobs
      .filter((j) => (status === "all" ? true : j.status === status))
      .filter((j) => (engine === engineFilters[0] ? true : j.engine === engine))
      .filter((j) =>
        query.trim() === "" ? true : (j.name + j.id).toLowerCase().includes(query.toLowerCase()),
      )
      .sort((a, b) => {
        const dir = sortDir === "asc" ? 1 : -1;
        if (sortBy === "progress") return (a.progress - b.progress) * dir;
        if (sortBy === "duration") return (a.duration ?? "").localeCompare(b.duration ?? "") * dir;
        return a.createdAt.localeCompare(b.createdAt) * dir;
      });
  }, [jobs, status, engine, query, sortBy, sortDir]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const flipSort = (key: typeof sortBy) => {
    if (sortBy === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortBy(key);
      setSortDir("desc");
    }
  };

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow={jobs.length === 0 ? "No jobs" : `${filtered.length} of ${jobs.length} results`}
        title="Jobs"
        description="Reconstruction jobs across the workspace. Filter, sort, and inspect each execution."
        actions={
          <>
            <ButtonPro variant="outline" reason="CSV export is not implemented yet">
              Export CSV
            </ButtonPro>
            <ButtonPro variant="bronze" onClick={() => void createNewJob()}>
              Create New Job
            </ButtonPro>
          </>
        }
      />

      <div className="flex-1 p-6">
        <Panel bodyClassName="p-0" className="overflow-hidden">
          <div className="hairline-b flex flex-wrap items-center gap-2 bg-surface/40 px-4 py-2.5">
            <div className="relative w-72">
              <Search
                className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
                strokeWidth={1.6}
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name or ID…"
                className="mono h-8 w-full rounded-sm border border-border bg-surface-2 pl-8 pr-2 text-[12px] text-ivory placeholder:text-subtle focus:border-border-strong focus:outline-none"
              />
            </div>

            <div className="flex items-center gap-1 rounded-sm border border-border bg-surface-2 p-0.5">
              {statuses.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={cn(
                    "px-2.5 py-1 text-[10px] uppercase tracking-widest rounded-sm",
                    status === s
                      ? "bg-selected/12 text-ivory ring-1 ring-selected/35"
                      : "text-muted-foreground hover:text-ivory",
                  )}
                >
                  {s}
                </button>
              ))}
            </div>

            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              className="mono h-8 rounded-sm border border-border bg-surface-2 px-2 text-[11px] text-ivory"
            >
              {engineFilters.map((e) => (
                <option key={e}>{e}</option>
              ))}
            </select>

            <div className="flex-1" />

            {selected.size > 0 && (
              <div className="mono flex items-center gap-2 rounded-sm border border-bronze/40 bg-bronze/10 px-2 py-1 text-[11px] text-bronze">
                {selected.size} selected
                <button className="hover:text-ivory">
                  <Play className="h-3 w-3" />
                </button>
                <button className="hover:text-ivory">
                  <Pause className="h-3 w-3" />
                </button>
                <button className="hover:text-ivory">
                  <Download className="h-3 w-3" />
                </button>
                <button className="hover:text-ivory">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            )}

            <ButtonPro
              size="sm"
              variant="ghost"
              reason="Additional filters are not implemented yet"
            >
              <Filter className="h-3 w-3" /> More filters
            </ButtonPro>
          </div>

          {filtered.length === 0 ? (
            <EmptyState
              title="No reconstruction jobs yet."
              description="Create a job to begin uploading images and running the reconstruction pipeline."
              action={
                <ButtonPro variant="bronze" onClick={() => void createNewJob()}>
                  Create New Job
                </ButtonPro>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] text-[12px]">
                <thead>
                  <tr className="hairline-b bg-surface/60 text-[10px] uppercase tracking-widest text-subtle">
                    <th className="w-8 px-3 py-2 text-left"></th>
                    <Th onClick={() => flipSort("createdAt")}>ID</Th>
                    <th className="px-3 py-2 text-left">Name</th>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-left">Engine</th>
                    <Th onClick={() => flipSort("progress")}>Progress</Th>
                    <Th onClick={() => flipSort("createdAt")}>Created</Th>
                    <Th onClick={() => flipSort("duration")}>Duration</Th>
                    <th className="px-3 py-2 text-left">Owner</th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((j) => {
                    const isSel = selected.has(j.id);
                    return (
                      <tr
                        key={j.id}
                        className={cn(
                          "hairline-b transition-colors",
                          isSel ? "bg-selected/6" : "hover:bg-surface-2/60",
                        )}
                      >
                        <td className="px-3 py-2.5">
                          <input
                            type="checkbox"
                            checked={isSel}
                            onChange={() => toggle(j.id)}
                            className="h-3.5 w-3.5 accent-bronze"
                          />
                        </td>
                        <td className="mono px-3 py-2.5 text-bronze">{j.id}</td>
                        <td className="px-3 py-2.5">
                          <div className="text-ivory">{j.name}</div>
                          <div className="mono text-[10px] text-subtle">{j.images ?? 0} images</div>
                        </td>
                        <td className="px-3 py-2.5">
                          <StatusBadge status={j.status} />
                        </td>
                        <td className="mono px-3 py-2.5 text-muted-foreground">{j.engine}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-2">
                            <ProgressBar
                              value={j.progress}
                              tone={
                                j.status === "failed"
                                  ? "destructive"
                                  : j.status === "completed"
                                    ? "success"
                                    : "bronze"
                              }
                              className="w-32"
                            />
                            <span className="mono w-10 text-right text-[10px] text-subtle">
                              {j.progress}%
                            </span>
                          </div>
                        </td>
                        <td className="mono px-3 py-2.5 text-muted-foreground">{j.createdAt}</td>
                        <td className="mono px-3 py-2.5 text-muted-foreground">
                          {j.duration ?? "—"}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className="mono text-[11px] text-muted-foreground">
                            {j.owner ?? "—"}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right">
                          <div className="inline-flex items-center gap-1">
                            <IconBtn
                              label={`Open ${j.id} on the dashboard`}
                              onClick={() => {
                                void openExistingJob(j.id);
                                void router.navigate({ to: "/" });
                              }}
                            >
                              <Play className="h-3 w-3" />
                            </IconBtn>
                            <IconBtn
                              label={`Open ${j.id} exports in the viewer`}
                              onClick={() => {
                                void openExistingJob(j.id);
                                void router.navigate({ to: "/viewer" });
                              }}
                            >
                              <Download className="h-3 w-3" />
                            </IconBtn>
                            <IconBtn label="Deleting jobs is not implemented yet" disabled>
                              <Trash2 className="h-3 w-3" />
                            </IconBtn>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {filtered.length > 0 && (
            <div className="flex items-center justify-between bg-surface/40 px-4 py-2 text-[11px] text-subtle">
              <span className="mono">Showing {filtered.length} rows</span>
              <div className="flex items-center gap-2">
                <button className="rounded-sm border border-border px-2 py-1 hover:bg-surface-2">
                  Prev
                </button>
                <span className="mono">1 / 1</span>
                <button className="rounded-sm border border-border px-2 py-1 hover:bg-surface-2">
                  Next
                </button>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Th({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <th className="px-3 py-2 text-left">
      <button onClick={onClick} className="inline-flex items-center gap-1 hover:text-ivory">
        {children}
        <ArrowUpDown className="h-3 w-3 opacity-60" />
      </button>
    </th>
  );
}

function IconBtn({
  children,
  label,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className="grid h-6 w-6 place-items-center rounded-sm border border-border text-muted-foreground hover:border-border-strong hover:text-ivory disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-border disabled:hover:text-muted-foreground"
    >
      {children}
    </button>
  );
}
