// Text-to-3D is listed but can never be submitted; settings persist only valid values.
import assert from "node:assert/strict";
import { test } from "node:test";
import { ENGINE_OPTIONS, isSubmittableEngine } from "../src/lib/engines.ts";
import { createNewJob } from "../src/lib/jobActions.ts";
import {
  normalizeBackendUrl,
  parseStoredSettings,
  serializeSettings,
} from "../src/lib/settingsStorage.ts";
import { DEFAULT_SETTINGS, useAppStore } from "../src/store/useAppStore.ts";
import type { EngineId } from "../src/types/index.ts";

test("Text-to-3D is visible as work in progress and is not submittable", () => {
  const ids = ENGINE_OPTIONS.map((o) => o.id);
  assert.deepEqual(ids, ["Instant-NGP", "Text-to-3D"]);
  assert.equal(ENGINE_OPTIONS[1].availability, "wip");
  assert.match(ENGINE_OPTIONS[1].description, /not available/);
  assert.equal(isSubmittableEngine("Instant-NGP"), true);
  assert.equal(isSubmittableEngine("Text-to-3D"), false);
});

test("creating a job with Text-to-3D sends no request", async () => {
  let requests = 0;
  globalThis.fetch = (async () => {
    requests++;
    return new Response("{}");
  }) as typeof fetch;
  const s = useAppStore.getState();
  s.setBackendStatus("connected");
  s.setSelectedEngine("Text-to-3D" as EngineId);
  assert.equal(await createNewJob(), null);
  assert.equal(requests, 0);
  s.setSelectedEngine("Instant-NGP");
});

test("creating a job while the backend is offline sends no request", async () => {
  let requests = 0;
  globalThis.fetch = (async () => {
    requests++;
    return new Response("{}");
  }) as typeof fetch;
  useAppStore.getState().setBackendStatus("disconnected");
  assert.equal(await createNewJob(), null);
  assert.equal(requests, 0);
});

test("backend URLs must be plain http(s) origins or paths", () => {
  assert.equal(normalizeBackendUrl(" http://localhost:8000/ "), "http://localhost:8000");
  assert.equal(
    normalizeBackendUrl("https://api.example.org/base/"),
    "https://api.example.org/base",
  );
  for (const bad of [
    "",
    "localhost:8000",
    "ftp://x",
    "javascript:alert(1)",
    "http://u:p@h",
    "http://h/?x=1",
  ]) {
    assert.equal(normalizeBackendUrl(bad), null, bad);
  }
});

test("stored settings: valid values load, malformed ones fall back to defaults", () => {
  const stored = serializeSettings({
    ...DEFAULT_SETTINGS,
    backendUrl: "http://127.0.0.1:9000",
    denseTables: true,
    terminalOnLaunch: false,
  });
  const loaded = parseStoredSettings(stored, DEFAULT_SETTINGS);
  assert.equal(loaded.backendUrl, "http://127.0.0.1:9000");
  assert.equal(loaded.denseTables, true);
  assert.equal(loaded.terminalOnLaunch, false);
  assert.deepEqual(parseStoredSettings("{oops", DEFAULT_SETTINGS), DEFAULT_SETTINGS);
  const tampered = parseStoredSettings(
    JSON.stringify({ backendUrl: "javascript:x", defaultEngine: "Text-to-3D", denseTables: "yes" }),
    DEFAULT_SETTINGS,
  );
  assert.deepEqual(tampered, DEFAULT_SETTINGS);
});
