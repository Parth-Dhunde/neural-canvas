// Jobs table: filters, sorting, paging, CSV export and which jobs may be deleted.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  DEFAULT_JOB_FILTERS,
  activeExtraFilterCount,
  applyDeletedJobs,
  filterJobs,
  jobsToCsv,
  paginate,
  sortJobs,
  splitDeletable,
} from "../src/lib/jobTable.ts";
import type { Job } from "../src/types/index.ts";

const NOW = Date.parse("2026-11-21T12:00:00Z");

function job(id: string, overrides: Partial<Job> = {}): Job {
  return {
    id,
    name: `Object ${id.slice(-1)}`,
    engine: "Instant-NGP",
    status: "completed",
    progress: 100,
    createdAt: "2026-11-20T12:00:00Z",
    ...overrides,
  };
}

const jobs = [
  job("job_000001", {
    status: "failed",
    progress: 40,
    trainingDurationSeconds: 900,
    createdAt: "2026-10-01T00:00:00Z",
  }),
  job("job_000002", {
    status: "running",
    progress: 55,
    jobOutputs: { mesh: true, cleanedMesh: false, exports: {} },
  }),
  job("job_000003", {
    trainingDurationSeconds: 1260,
    jobOutputs: { mesh: true, cleanedMesh: true, exports: { cleaned: ["glb"] } },
  }),
  job("job_000004", { status: "waiting", progress: 0, name: "Red mug" }),
];

test("status, engine, query and extra filters combine", () => {
  const f = { ...DEFAULT_JOB_FILTERS };
  assert.equal(filterJobs(jobs, { ...f, status: "failed" }, NOW).length, 1);
  assert.deepEqual(
    filterJobs(jobs, { ...f, query: "red" }, NOW).map((j) => j.id),
    ["job_000004"],
  );
  assert.deepEqual(
    filterJobs(jobs, { ...f, query: "000003" }, NOW).map((j) => j.id),
    ["job_000003"],
  );
  assert.equal(filterJobs(jobs, { ...f, engine: "Text-to-3D" }, NOW).length, 0);
  assert.deepEqual(
    filterJobs(jobs, { ...f, outputs: "mesh" }, NOW).map((j) => j.id),
    ["job_000002", "job_000003"],
  );
  assert.deepEqual(
    filterJobs(jobs, { ...f, outputs: "exports" }, NOW).map((j) => j.id),
    ["job_000003"],
  );
  assert.deepEqual(
    filterJobs(jobs, { ...f, outputs: "none" }, NOW).map((j) => j.id),
    ["job_000001", "job_000004"],
  );
  assert.equal(filterJobs(jobs, { ...f, created: "7d" }, NOW).length, 3);
  assert.equal(activeExtraFilterCount({ ...f, outputs: "mesh", created: "24h" }), 2);
});

test("training duration sorts numerically, not as text", () => {
  const sorted = sortJobs(jobs, "duration", "desc").map((j) => j.id);
  assert.deepEqual(sorted.slice(0, 2), ["job_000003", "job_000001"]);
  assert.deepEqual(
    sortJobs(jobs, "progress", "asc").map((j) => j.progress),
    [0, 40, 55, 100],
  );
  assert.equal(sortJobs(jobs, "createdAt", "asc")[0].id, "job_000001");
});

test("pagination clamps the page and reports the visible range", () => {
  const items = Array.from({ length: 23 }, (_, i) => i);
  assert.deepEqual(paginate(items, 3, 10), {
    items: [20, 21, 22],
    page: 3,
    pageCount: 3,
    start: 21,
    end: 23,
  });
  assert.equal(paginate(items, 99, 10).page, 3);
  assert.equal(paginate(items, 0, 10).page, 1);
  assert.deepEqual(paginate([], 1, 10), { items: [], page: 1, pageCount: 1, start: 0, end: 0 });
});

test("CSV escapes quotes and commas and neutralises formulas", () => {
  const csv = jobsToCsv([
    job("job_000009", { name: 'He said "hi", twice', lastError: "=cmd|' /C calc'!A0" }),
  ]);
  const [header, row] = csv.trim().split("\r\n");
  assert.ok(header.startsWith("id,name,status,engine"));
  assert.ok(row.includes('"He said ""hi"", twice"'));
  assert.ok(row.includes("'=cmd"));
  assert.ok(!row.includes(",=cmd"));
});

test("running jobs are never offered for deletion", () => {
  assert.deepEqual(splitDeletable(jobs, ["job_000001", "job_000002", "job_000003", "missing"]), {
    deletable: ["job_000001", "job_000003"],
    running: ["job_000002"],
  });
});

test("applying a deletion updates list, active job and viewer selection", () => {
  const view = { jobs, currentJob: jobs[2], viewerJobId: "job_000003" };
  const next = applyDeletedJobs(view, ["job_000003", "job_000001"]);
  assert.deepEqual(
    next.jobs.map((j) => j.id),
    ["job_000002", "job_000004"],
  );
  assert.equal(next.currentJob?.id, "job_000002");
  assert.equal(next.viewerJobId, null);
  const untouched = applyDeletedJobs(view, ["job_000004"]);
  assert.equal(untouched.currentJob?.id, "job_000003");
  assert.equal(untouched.viewerJobId, "job_000003");
});
