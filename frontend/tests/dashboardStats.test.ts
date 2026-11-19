// Dashboard statistics display rules (run with `npm test`).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  NOT_RECORDED,
  UNAVAILABLE,
  formatBytes,
  formatDuration,
  formatMedianStatistic,
  isActiveJob,
  jobsSignature,
  pipelineSnapshotMetrics,
} from "../src/lib/dashboardStats.ts";
import type { MedianStatisticApi } from "../src/services/dashboard.ts";
import type { Job } from "../src/types/index.ts";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job_000006",
    name: "job_000006",
    engine: "Instant-NGP",
    status: "completed",
    progress: 100,
    createdAt: "2026-09-19T01:52:29+00:00",
    logs: [],
    outputs: [],
    metrics: [],
    ...overrides,
  };
}

const TRAINED = job({
  trainingDurationSeconds: 1270.17,
  trainingMetrics: {
    finalLoss: 0.00029,
    lastLoggedStep: 34998,
    totalSteps: 35000,
    meanStepsPerSecond: 27.623,
    checkpointCount: 1,
    peakVramMib: null,
    source: "training_log",
  },
});

test("completed and failed jobs are not active; queued and running are", () => {
  assert.equal(isActiveJob("completed"), false);
  assert.equal(isActiveJob("failed"), false);
  assert.equal(isActiveJob("cancelled"), false);
  assert.equal(isActiveJob("waiting"), false);
  assert.equal(isActiveJob("queued"), true);
  assert.equal(isActiveJob("running"), true);
});

test("pipeline snapshot shows the job's recorded training metrics", () => {
  const [loss, throughput, checkpoints, vram, elapsed, pipeline] = pipelineSnapshotMetrics(TRAINED);
  assert.equal(loss.value, "2.90e-4");
  assert.match(loss.hint, /34,998\/35,000/);
  assert.equal(throughput.label, "Throughput");
  assert.equal(throughput.value, "27.6 steps/s");
  assert.doesNotMatch(throughput.value, /rays/i);
  assert.equal(checkpoints.value, "1");
  assert.equal(elapsed.value, "21m 10s");
  assert.ok([loss, throughput, checkpoints, elapsed].every((m) => m.available));
  // Historical run (backfilled from training.log): VRAM and stage timings were never captured.
  assert.equal(vram.value, NOT_RECORDED);
  assert.equal(pipeline.value, NOT_RECORDED);
});

test("new runs show recorded peak VRAM and total pipeline time", () => {
  const [, , , vram, , pipeline] = pipelineSnapshotMetrics({
    ...TRAINED,
    pipelineDurationSeconds: 1295,
    trainingMetrics: { ...TRAINED.trainingMetrics!, peakVramMib: 1344, source: "pipeline" },
  });
  assert.equal(vram.value, "1.31 GB");
  assert.equal(pipeline.value, "21m 35s");
});

test("missing metrics are N/A with a reason, never a default number", () => {
  const metrics = pipelineSnapshotMetrics(job({ status: "waiting", progress: 29 }));
  for (const m of metrics) {
    assert.equal(m.value, UNAVAILABLE);
    assert.equal(m.available, false);
    assert.ok(m.hint.length > 0);
  }
  const partial = pipelineSnapshotMetrics(
    job({ trainingMetrics: { ...TRAINED.trainingMetrics!, finalLoss: null } }),
  );
  assert.equal(partial[0].value, NOT_RECORDED);
  assert.equal(pipelineSnapshotMetrics(null)[0].value, "—");
});

test("median statistics show sample size, or the backend's unavailable reason", () => {
  const psnr: MedianStatisticApi = {
    statistic: "median",
    value: 36.73,
    unit: "dB",
    sample_size: 1,
    unavailable_reason: null,
  };
  assert.deepEqual(
    formatMedianStatistic(psnr, (v) => `${v.toFixed(2)} dB`, "evaluated"),
    {
      value: "36.73 dB",
      hint: "Median · 1 evaluated job",
      available: true,
    },
  );

  const none = formatMedianStatistic(
    { ...psnr, value: null, sample_size: 0, unavailable_reason: "not evaluated" },
    String,
  );
  assert.deepEqual(none, { value: UNAVAILABLE, hint: "not evaluated", available: false });
  assert.equal(formatMedianStatistic(undefined, String).available, false);
  assert.equal(
    formatMedianStatistic(
      { ...psnr, value: null, sample_size: 0 },
      String,
      "evaluated",
      "Not evaluated",
    ).value,
    "Not evaluated",
  );
});

test("job signature changes when a job completes, so the dashboard refetches", () => {
  const running = [job({ status: "running", progress: 60 })];
  const done = [job({ status: "completed", progress: 100 })];
  assert.notEqual(jobsSignature(running), jobsSignature(done));
  assert.equal(jobsSignature(done), jobsSignature([job()]));
});

test("formatting helpers", () => {
  assert.equal(formatDuration(45), "45s");
  assert.equal(formatDuration(3725), "1h 02m");
  assert.equal(formatBytes(345937525), "330 MB");
  assert.equal(formatBytes(-1), UNAVAILABLE);
});
