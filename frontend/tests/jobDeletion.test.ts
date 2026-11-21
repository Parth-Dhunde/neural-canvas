// Job deletion from the UI: store updates for single, bulk, refused and failed deletions.
import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { deleteJobsById } from "../src/lib/jobActions.ts";
import { BackendUnreachableError, onBackendUnreachable } from "../src/services/api.ts";
import { useAppStore } from "../src/store/useAppStore.ts";
import type { Job } from "../src/types/index.ts";

function job(id: string, status: Job["status"] = "completed"): Job {
  return {
    id,
    name: id,
    engine: "Instant-NGP",
    status,
    progress: 0,
    createdAt: "2026-11-01T00:00:00Z",
  };
}

interface Call {
  method: string;
  url: string;
  body?: unknown;
}
let calls: Call[] = [];
let bulkResults: { job_id: string; status: string; detail: string | null }[] = [];
let failNetwork = false;
let failStatus: number | null = null;

globalThis.fetch = (async (input: string | URL, init?: RequestInit) => {
  const url = String(input);
  const method = init?.method ?? "GET";
  calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
  if (failNetwork) throw new TypeError("Failed to fetch");
  const json = (status: number, payload: unknown) =>
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  if (url.endsWith("/api/jobs/bulk-delete")) {
    if (failStatus) return json(failStatus, { detail: "Disk is read-only" });
    return json(200, {
      results: bulkResults,
      deleted: bulkResults.filter((r) => r.status === "deleted").length,
    });
  }
  if (url.endsWith("/api/jobs")) return json(200, { jobs: [], total: 0 });
  if (url.includes("/pipeline")) return json(404, { detail: "nope" });
  return json(404, { detail: "unexpected" });
}) as typeof fetch;

beforeEach(() => {
  calls = [];
  bulkResults = [];
  failNetwork = false;
  failStatus = null;
  const s = useAppStore.getState();
  s.setBackendStatus("connected");
  s.setJobs([job("job_000001"), job("job_000002", "failed"), job("job_000003", "waiting")]);
  s.setCurrentJob(useAppStore.getState().jobs[0]);
  s.setViewer({ selectedJobId: "job_000001" });
});

test("single deletion removes the job from every view and moves the active job", async () => {
  bulkResults = [{ job_id: "job_000001", status: "deleted", detail: null }];
  const summary = await deleteJobsById(["job_000001"]);
  assert.deepEqual(summary.deleted, ["job_000001"]);
  assert.deepEqual(summary.problems, []);
  const s = useAppStore.getState();
  assert.deepEqual(
    s.jobs.map((j) => j.id),
    ["job_000002", "job_000003"],
  );
  assert.equal(s.currentJob?.id, "job_000002");
  assert.equal(s.viewer.selectedJobId, null);
  const del = calls.find((c) => c.url.endsWith("/bulk-delete"));
  assert.deepEqual(del?.body, { job_ids: ["job_000001"] });
  assert.equal(del?.method, "POST");
});

test("bulk deletion keeps refused and failed jobs and reports them", async () => {
  bulkResults = [
    { job_id: "job_000001", status: "deleted", detail: null },
    { job_id: "job_000002", status: "not_found", detail: "Job not found" },
    { job_id: "job_000003", status: "refused", detail: "job_000003 is running. Cancel the run…" },
  ];
  const summary = await deleteJobsById(["job_000001", "job_000002", "job_000003"]);
  assert.deepEqual(summary.deleted, ["job_000001", "job_000002"]);
  assert.deepEqual(
    summary.problems.map((p) => p.job_id),
    ["job_000003"],
  );
  assert.deepEqual(
    useAppStore.getState().jobs.map((j) => j.id),
    ["job_000003"],
  );
  assert.equal(useAppStore.getState().currentJob?.id, "job_000003");
});

test("deleting a job that is not active keeps the active job", async () => {
  bulkResults = [{ job_id: "job_000003", status: "deleted", detail: null }];
  await deleteJobsById(["job_000003"]);
  const s = useAppStore.getState();
  assert.equal(s.currentJob?.id, "job_000001");
  assert.equal(s.viewer.selectedJobId, "job_000001");
});

test("a network failure leaves every job in place and triggers a health recheck", async () => {
  failNetwork = true;
  let rechecks = 0;
  const unsubscribe = onBackendUnreachable(() => rechecks++);
  await assert.rejects(deleteJobsById(["job_000001"]), BackendUnreachableError);
  unsubscribe();
  assert.equal(rechecks, 1);
  assert.equal(useAppStore.getState().jobs.length, 3);
  assert.equal(useAppStore.getState().currentJob?.id, "job_000001");
});

test("a server error is reported with its detail and changes nothing", async () => {
  failStatus = 500;
  await assert.rejects(deleteJobsById(["job_000002"]), /Disk is read-only/);
  assert.equal(useAppStore.getState().jobs.length, 3);
});

test("no request is sent while the backend is offline", async () => {
  useAppStore.getState().setBackendStatus("disconnected");
  await assert.rejects(deleteJobsById(["job_000001"]), /offline/);
  assert.equal(calls.length, 0);
  assert.equal(useAppStore.getState().jobs.length, 3);
});

test("an empty selection sends nothing", async () => {
  const summary = await deleteJobsById([]);
  assert.deepEqual(summary, { deleted: [], problems: [] });
  assert.equal(calls.length, 0);
});
