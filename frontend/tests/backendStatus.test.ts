// Backend availability: transient failures show "checking"; only repeated failures go offline.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  HEALTH_TIMING,
  initialHealthTracker,
  nextHealthDelayMs,
  recordHealthResult,
  type HealthTracker,
} from "../src/lib/backendStatus.ts";

const run = (results: boolean[], start: HealthTracker = initialHealthTracker()) =>
  results.reduce((t, ok) => recordHealthResult(t, ok), start);

test("starts in checking, connects on the first success (backend running at load)", () => {
  assert.equal(initialHealthTracker().phase, "checking");
  assert.equal(run([true]).phase, "connected");
});

test("backend offline at load is confirmed only after three failures", () => {
  assert.equal(run([false]).phase, "checking");
  assert.equal(run([false, false]).phase, "checking");
  assert.equal(run([false, false, false]).phase, "disconnected");
});

test("a single failure while connected shows checking, not offline", () => {
  const blip = run([true, false]);
  assert.equal(blip.phase, "checking");
  assert.equal(nextHealthDelayMs(blip), HEALTH_TIMING.retryIntervalMs);
});

test("temporary network failure that recovers never reports offline", () => {
  let t = run([true]);
  const phases: string[] = [];
  for (const ok of [false, false, true]) {
    t = recordHealthResult(t, ok);
    phases.push(t.phase);
  }
  assert.deepEqual(phases, ["checking", "checking", "connected"]);
});

test("disconnect while open, then reconnect, without a reload", () => {
  const offline = run([true, false, false, false]);
  assert.equal(offline.phase, "disconnected");
  assert.equal(recordHealthResult(offline, false).phase, "disconnected");
  assert.equal(recordHealthResult(offline, true).phase, "connected");
});

test("check intervals: steady when connected, quick retries, backoff when offline", () => {
  assert.equal(nextHealthDelayMs(run([true])), HEALTH_TIMING.connectedIntervalMs);
  const offline = run([false, false, false]);
  assert.equal(nextHealthDelayMs(offline), HEALTH_TIMING.offlineIntervalMs);
  assert.equal(nextHealthDelayMs(run([false], offline)), HEALTH_TIMING.offlineIntervalMs * 2);
  assert.equal(
    nextHealthDelayMs(run([false, false, false, false, false], offline)),
    HEALTH_TIMING.offlineMaxIntervalMs,
  );
});
