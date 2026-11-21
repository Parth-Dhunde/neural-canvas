import { createFileRoute, useNavigate, useRouter } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowUpDown,
  Download,
  Eye,
  Filter,
  LayoutDashboard,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader, Panel, ButtonPro } from "@/components/ui-pro/Panel";
import { ConfirmDialog } from "@/components/ui-pro/ConfirmDialog";
import { EmptyState } from "@/components/ui-pro/EmptyState";
import { StatusBadge } from "@/components/ui-pro/StatusBadge";
import { ProgressBar } from "@/components/ui-pro/ProgressBar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { SUPPORTED_ENGINES } from "@/lib/constants";
import { downloadTextFile } from "@/lib/download";
import {
  DEFAULT_JOB_FILTERS,
  activeExtraFilterCount,
  filterJobs,
  jobsToCsv,
  paginate,
  sortJobs,
  splitDeletable,
  type CreatedFilter,
  type JobFilters,
  type JobSortKey,
  type OutputsFilter,
  type SortDirection,
} from "@/lib/jobTable";
import {
  backendUnavailableReasonFor,
  createNewJob,
  deleteJobsById,
  openExistingJob,
} from "@/lib/jobActions";
import { useAppStore } from "@/store/useAppStore";
import type { Job, JobStatus } from "@/types";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/jobs")({
  component: JobsPage,
  validateSearch: (search: Record<string, unknown>): { q?: string } =>
    typeof search.q === "string" && search.q.trim() ? { q: search.q } : {},
  head: () => ({
    meta: [
      { title: "Jobs — NeuralCanvas" },
      { name: "description", content: "Manage, filter, export and delete reconstruction jobs." },
    ],
  }),
});

const STATUS_FILTERS: (JobStatus | "all")[] = [
  "all",
  "waiting",
  "running",
  "paused",
  "completed",
  "failed",
  "cancelled",
];
const PAGE_SIZES = [10, 25, 50] as const;

function formatCreated(iso: string): string {
  const time = Date.parse(iso);
  return Number.isNaN(time) ? iso : new Date(time).toLocaleString();
}

function JobsPage() {
  const router = useRouter();
  const navigate = useNavigate({ from: "/jobs" });
  const search = Route.useSearch();
  const jobs = useAppStore((s) => s.jobs);
  const dense = useAppStore((s) => s.settings.denseTables);
  const backendStatus = useAppStore((s) => s.backendHealth.status);
  const offlineReason = backendUnavailableReasonFor(backendStatus);

  const [filters, setFilters] = useState<JobFilters>({
    ...DEFAULT_JOB_FILTERS,
    query: search.q ?? "",
  });
  const [sortBy, setSortBy] = useState<JobSortKey>("createdAt");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(25);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);

  // The top-bar search navigates here with ?q=…
  useEffect(() => {
    setFilters((f) => (f.query === (search.q ?? "") ? f : { ...f, query: search.q ?? "" }));
  }, [search.q]);

  // Drop selections for jobs that no longer exist (deleted here or elsewhere).
  useEffect(() => {
    setSelected((prev) => {
      const ids = new Set(jobs.map((j) => j.id));
      const next = new Set([...prev].filter((id) => ids.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [jobs]);

  const filtered = useMemo(
    () => sortJobs(filterJobs(jobs, filters), sortBy, sortDir),
    [jobs, filters, sortBy, sortDir],
  );
  const pageData = paginate(filtered, page, pageSize);
  const pageIds = pageData.items.map((j) => j.id);
  const selectedOnPage = pageIds.filter((id) => selected.has(id)).length;
  const allOnPageSelected = pageIds.length > 0 && selectedOnPage === pageIds.length;

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedOnPage > 0 && !allOnPageSelected;
    }
  }, [selectedOnPage, allOnPageSelected]);

  useEffect(() => setPage(1), [filters, pageSize]);

  const updateFilters = (patch: Partial<JobFilters>) => setFilters((f) => ({ ...f, ...patch }));

  const setQuery = (query: string) => {
    updateFilters({ query });
    void navigate({ search: query.trim() ? { q: query } : {}, replace: true });
  };

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleAllOnPage = () =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (allOnPageSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });

  const flipSort = (key: JobSortKey) => {
    if (sortBy === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortBy(key);
      setSortDir("desc");
    }
  };

  const exportCsv = (rows: Job[], label: string) => {
    if (rows.length === 0) {
      toast.error("Nothing to export");
      return;
    }
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    downloadTextFile(`neuralcanvas-jobs-${label}-${stamp}.csv`, jobsToCsv(rows), "text/csv");
    toast.success(`Exported ${rows.length} job${rows.length === 1 ? "" : "s"} to CSV`);
  };

  const requestDelete = (ids: string[]) => {
    const { deletable, running } = splitDeletable(jobs, ids);
    if (deletable.length === 0) {
      toast.error("Running jobs cannot be deleted", {
        description: "Cancel the run on the dashboard and wait for it to stop, then delete.",
      });
      return;
    }
    if (running.length > 0) {
      toast.message(
        `${running.length} running job${running.length === 1 ? " is" : "s are"} skipped`,
        {
          description: running.join(", "),
        },
      );
    }
    setDeleteError(null);
    setPendingDelete(deletable);
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const { deleted, problems } = await deleteJobsById(pendingDelete);
      setSelected((prev) => new Set([...prev].filter((id) => !deleted.includes(id))));
      if (deleted.length > 0) {
        toast.success(`Deleted ${deleted.length} job${deleted.length === 1 ? "" : "s"}`);
      }
      if (problems.length > 0) {
        setPendingDelete(problems.map((p) => p.job_id));
        setDeleteError(problems.map((p) => `${p.job_id}: ${p.detail ?? p.status}`).join("\n"));
      } else {
        setPendingDelete(null);
      }
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "Deletion failed");
    } finally {
      setDeleting(false);
    }
  };

  const pendingJobs = jobs.filter((j) => pendingDelete?.includes(j.id));
  const extraFilters = activeExtraFilterCount(filters);
  const cell = dense ? "px-3 py-1.5" : "px-3 py-2.5";

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        eyebrow={jobs.length === 0 ? "No jobs" : `${filtered.length} of ${jobs.length} results`}
        title="Jobs"
        description="Reconstruction jobs across the workspace. Filter, sort, export, open and delete jobs."
        actions={
          <>
            <ButtonPro
              variant="outline"
              onClick={() => exportCsv(filtered, "filtered")}
              reason={filtered.length === 0 ? "No jobs match the current filters" : undefined}
            >
              <Download className="h-3 w-3" /> Export CSV
            </ButtonPro>
            <ButtonPro variant="bronze" reason={offlineReason} onClick={() => void createNewJob()}>
              Create New Job
            </ButtonPro>
          </>
        }
      />

      <div className="flex-1 p-4 sm:p-6">
        <Panel bodyClassName="p-0" className="overflow-visible">
          <div className="hairline-b flex flex-wrap items-center gap-2 bg-surface/40 px-4 py-2.5">
            <div className="relative w-full sm:w-72">
              <Search
                className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-subtle"
                strokeWidth={1.6}
              />
              <input
                value={filters.query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name or ID…"
                aria-label="Search jobs by name or ID"
                className="mono h-8 w-full rounded-sm border border-border bg-surface-2 pl-8 pr-7 text-[12px] text-ivory placeholder:text-subtle focus:border-border-strong focus:outline-none"
              />
              {filters.query && (
                <button
                  type="button"
                  aria-label="Clear search"
                  onClick={() => setQuery("")}
                  className="absolute right-1.5 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center rounded-sm text-subtle hover:text-ivory"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>

            <div
              role="group"
              aria-label="Filter by status"
              className="flex flex-wrap items-center gap-1 rounded-sm border border-border bg-surface-2 p-0.5"
            >
              {STATUS_FILTERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={filters.status === s}
                  onClick={() => updateFilters({ status: s })}
                  className={cn(
                    "rounded-sm px-2.5 py-1 text-[10px] uppercase tracking-widest",
                    filters.status === s
                      ? "bg-selected/12 text-ivory ring-1 ring-selected/35"
                      : "text-muted-foreground hover:text-ivory",
                  )}
                >
                  {s}
                </button>
              ))}
            </div>

            <select
              value={filters.engine}
              onChange={(e) => updateFilters({ engine: e.target.value })}
              aria-label="Filter by engine"
              className="mono h-8 rounded-sm border border-border bg-surface-2 px-2 text-[11px] text-ivory"
            >
              <option value="all">All engines</option>
              {SUPPORTED_ENGINES.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>

            <Popover>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className={cn(
                    "inline-flex h-7 items-center gap-1.5 rounded-sm px-2.5 text-[11px] font-medium uppercase tracking-wider hover:bg-surface-2 hover:text-ivory",
                    extraFilters ? "text-bronze" : "text-muted-foreground",
                  )}
                >
                  <Filter className="h-3 w-3" /> More filters
                  {extraFilters ? ` (${extraFilters})` : ""}
                </button>
              </PopoverTrigger>
              <PopoverContent align="start" className="w-64 border-border bg-popover p-3">
                <div className="space-y-3 text-[12px]">
                  <label className="block space-y-1">
                    <span className="label-caps">Outputs</span>
                    <select
                      value={filters.outputs}
                      onChange={(e) => updateFilters({ outputs: e.target.value as OutputsFilter })}
                      className="mono h-8 w-full rounded-sm border border-border bg-surface-2 px-2 text-[11px] text-ivory"
                    >
                      <option value="any">Any</option>
                      <option value="mesh">Has a mesh</option>
                      <option value="exports">Has exports</option>
                      <option value="none">No outputs yet</option>
                    </select>
                  </label>
                  <label className="block space-y-1">
                    <span className="label-caps">Created</span>
                    <select
                      value={filters.created}
                      onChange={(e) => updateFilters({ created: e.target.value as CreatedFilter })}
                      className="mono h-8 w-full rounded-sm border border-border bg-surface-2 px-2 text-[11px] text-ivory"
                    >
                      <option value="any">Any time</option>
                      <option value="24h">Last 24 hours</option>
                      <option value="7d">Last 7 days</option>
                      <option value="30d">Last 30 days</option>
                    </select>
                  </label>
                  <ButtonPro
                    size="sm"
                    variant="ghost"
                    reason={extraFilters === 0 ? "No extra filters are active" : undefined}
                    onClick={() => updateFilters({ outputs: "any", created: "any" })}
                  >
                    Reset filters
                  </ButtonPro>
                </div>
              </PopoverContent>
            </Popover>

            <div className="flex-1" />

            {selected.size > 0 && (
              <div className="mono flex flex-wrap items-center gap-1.5 rounded-sm border border-bronze/40 bg-bronze/10 px-2 py-1 text-[11px] text-bronze">
                <span className="px-1">{selected.size} selected</span>
                <ButtonPro
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    exportCsv(
                      jobs.filter((j) => selected.has(j.id)),
                      "selected",
                    )
                  }
                >
                  <Download className="h-3 w-3" /> CSV
                </ButtonPro>
                <ButtonPro
                  size="sm"
                  variant="danger"
                  reason={offlineReason}
                  onClick={() => requestDelete([...selected])}
                >
                  <Trash2 className="h-3 w-3" /> Delete
                </ButtonPro>
                <ButtonPro size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                  Clear
                </ButtonPro>
              </div>
            )}
          </div>

          {filtered.length === 0 ? (
            jobs.length === 0 ? (
              <EmptyState
                title="No reconstruction jobs yet."
                description={
                  offlineReason
                    ? "Jobs are loaded from the backend, which is not connected right now."
                    : "Create a job to begin uploading images and running the reconstruction pipeline."
                }
                action={
                  <ButtonPro
                    variant="bronze"
                    reason={offlineReason}
                    onClick={() => void createNewJob()}
                  >
                    Create New Job
                  </ButtonPro>
                }
              />
            ) : (
              <EmptyState
                title="No jobs match these filters."
                action={
                  <ButtonPro variant="outline" onClick={() => setFilters(DEFAULT_JOB_FILTERS)}>
                    Clear filters
                  </ButtonPro>
                }
              />
            )
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[960px] text-[12px]">
                <thead>
                  <tr className="hairline-b bg-surface/60 text-[10px] uppercase tracking-widest text-subtle">
                    <th className="w-8 px-3 py-2 text-left">
                      <input
                        ref={selectAllRef}
                        type="checkbox"
                        checked={allOnPageSelected}
                        onChange={toggleAllOnPage}
                        aria-label="Select all jobs on this page"
                        className="h-3.5 w-3.5 accent-bronze"
                      />
                    </th>
                    <Th active={sortBy === "id"} dir={sortDir} onClick={() => flipSort("id")}>
                      ID
                    </Th>
                    <th className="px-3 py-2 text-left">Name</th>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-left">Engine</th>
                    <Th
                      active={sortBy === "progress"}
                      dir={sortDir}
                      onClick={() => flipSort("progress")}
                    >
                      Progress
                    </Th>
                    <Th
                      active={sortBy === "createdAt"}
                      dir={sortDir}
                      onClick={() => flipSort("createdAt")}
                    >
                      Created
                    </Th>
                    <Th
                      active={sortBy === "duration"}
                      dir={sortDir}
                      onClick={() => flipSort("duration")}
                    >
                      Training
                    </Th>
                    <th className="px-3 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {pageData.items.map((j) => {
                    const isSel = selected.has(j.id);
                    const running = j.status === "running";
                    const busy = deleting && pendingDelete?.includes(j.id);
                    return (
                      <tr
                        key={j.id}
                        aria-busy={busy || undefined}
                        className={cn(
                          "hairline-b transition-colors",
                          busy && "opacity-50",
                          isSel ? "bg-selected/6" : "hover:bg-surface-2/60",
                        )}
                      >
                        <td className={cell}>
                          <input
                            type="checkbox"
                            checked={isSel}
                            onChange={() => toggle(j.id)}
                            aria-label={`Select ${j.id}`}
                            className="h-3.5 w-3.5 accent-bronze"
                          />
                        </td>
                        <td className={cn(cell, "mono text-bronze")}>{j.id}</td>
                        <td className={cell}>
                          <div className="text-ivory">{j.name}</div>
                          {!dense && (
                            <div className="mono text-[10px] text-subtle">
                              {j.imageCount ?? 0} images
                            </div>
                          )}
                        </td>
                        <td className={cell}>
                          <StatusBadge status={j.status} />
                        </td>
                        <td className={cn(cell, "mono text-muted-foreground")}>{j.engine}</td>
                        <td className={cell}>
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
                        <td className={cn(cell, "mono text-muted-foreground")}>
                          {formatCreated(j.createdAt)}
                        </td>
                        <td className={cn(cell, "mono text-muted-foreground")}>
                          {j.duration ?? "—"}
                        </td>
                        <td className={cn(cell, "text-right")}>
                          <div className="inline-flex items-center gap-1">
                            <IconBtn
                              label={offlineReason ?? `Open ${j.id} on the dashboard`}
                              disabled={Boolean(offlineReason)}
                              onClick={() => {
                                void openExistingJob(j.id);
                                void router.navigate({ to: "/" });
                              }}
                            >
                              <LayoutDashboard className="h-3 w-3" />
                            </IconBtn>
                            <IconBtn
                              label={offlineReason ?? `Open ${j.id} in the viewer`}
                              disabled={Boolean(offlineReason)}
                              onClick={() => {
                                void openExistingJob(j.id);
                                void router.navigate({ to: "/viewer" });
                              }}
                            >
                              <Eye className="h-3 w-3" />
                            </IconBtn>
                            <IconBtn
                              danger
                              label={
                                offlineReason ??
                                (running
                                  ? `${j.id} is running — cancel the run before deleting`
                                  : `Delete ${j.id}`)
                              }
                              disabled={Boolean(offlineReason) || running || deleting}
                              onClick={() => requestDelete([j.id])}
                            >
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
            <div className="flex flex-wrap items-center justify-between gap-2 bg-surface/40 px-4 py-2 text-[11px] text-subtle">
              <span className="mono">
                Showing {pageData.start}–{pageData.end} of {filtered.length}
              </span>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1.5">
                  Rows
                  <select
                    value={pageSize}
                    onChange={(e) => setPageSize(Number(e.target.value))}
                    className="mono h-7 rounded-sm border border-border bg-surface-2 px-1.5 text-[11px] text-ivory"
                  >
                    {PAGE_SIZES.map((size) => (
                      <option key={size} value={size}>
                        {size}
                      </option>
                    ))}
                  </select>
                </label>
                <ButtonPro
                  size="sm"
                  variant="outline"
                  disabled={pageData.page <= 1}
                  onClick={() => setPage(pageData.page - 1)}
                >
                  Prev
                </ButtonPro>
                <span className="mono">
                  {pageData.page} / {pageData.pageCount}
                </span>
                <ButtonPro
                  size="sm"
                  variant="outline"
                  disabled={pageData.page >= pageData.pageCount}
                  onClick={() => setPage(pageData.page + 1)}
                >
                  Next
                </ButtonPro>
              </div>
            </div>
          )}
        </Panel>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title={
          pendingDelete && pendingDelete.length > 1
            ? `Delete ${pendingDelete.length} jobs?`
            : `Delete ${pendingDelete?.[0] ?? "job"}?`
        }
        confirmLabel={
          pendingDelete && pendingDelete.length > 1
            ? `Delete ${pendingDelete.length} jobs`
            : "Delete job"
        }
        busy={deleting}
        busyLabel="Deleting…"
        error={deleteError}
        onCancel={() => {
          if (!deleting) setPendingDelete(null);
        }}
        onConfirm={() => void confirmDelete()}
      >
        <p>
          This permanently removes the job&apos;s folder on the backend: uploaded and masked images,
          camera data, the trained model, meshes, exports and logs. It cannot be undone.
        </p>
        <ul className="mono max-h-40 space-y-0.5 overflow-y-auto text-[11px] text-ivory">
          {pendingJobs.slice(0, 12).map((j) => (
            <li key={j.id}>
              {j.id} · {j.name} · {j.status}
            </li>
          ))}
          {pendingJobs.length > 12 && (
            <li className="text-subtle">…and {pendingJobs.length - 12} more</li>
          )}
        </ul>
      </ConfirmDialog>
    </div>
  );
}

function Th({
  children,
  onClick,
  active,
  dir,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active: boolean;
  dir: SortDirection;
}) {
  return (
    <th
      className="px-3 py-2 text-left"
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "inline-flex items-center gap-1 uppercase hover:text-ivory",
          active && "text-ivory",
        )}
      >
        {children}
        <ArrowUpDown className={cn("h-3 w-3", active ? "opacity-100" : "opacity-50")} />
      </button>
    </th>
  );
}

function IconBtn({
  children,
  label,
  onClick,
  disabled,
  danger,
}: {
  children: React.ReactNode;
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  // Disabled buttons get no hover events, so the explanation lives on the wrapper.
  return (
    <span title={label} className={cn("inline-flex", disabled && "cursor-not-allowed")}>
      <button
        type="button"
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        className={cn(
          "grid h-6 w-6 place-items-center rounded-sm border border-border text-muted-foreground hover:border-border-strong hover:text-ivory disabled:pointer-events-none disabled:opacity-40",
          danger && "hover:border-destructive/60 hover:text-destructive",
        )}
      >
        {children}
      </button>
    </span>
  );
}
