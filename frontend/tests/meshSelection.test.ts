// Viewer mesh selection and visibility rules (run with `npm test`).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  downloadLinks,
  effectiveViewerTab,
  selectViewerMesh,
  viewableVariants,
  viewerJobs,
} from "../src/lib/meshSelection.ts";
import type { ExportManifestApi, ExportVariantApi } from "../src/services/exports.ts";
import type { Job } from "../src/types/index.ts";

const file = (variant: string, fmt: string, available = true, bytes = 100) => ({
  path: `x/mesh.${fmt}`,
  available,
  bytes,
  ...(available
    ? { url: `/api/jobs/job_1/exports/${variant}/${fmt}` }
    : { problem: "file not found" }),
});

function variant(
  name: string,
  available: boolean,
  cleanupId: string | null = null,
): ExportVariantApi {
  return {
    source: name === "cleaned" ? "stage6" : "stage5",
    formats: {
      glb: file(name, "glb", available),
      obj: file(name, "obj", available),
      ply: file(name, "ply", available),
    },
    complete: available,
    cleanup_id: cleanupId,
    unavailable_reason: available ? null : "mesh cleanup has not run",
  };
}

const manifest = (cleaned: boolean, original = true): ExportManifestApi => ({
  job_id: "job_1",
  preferred: cleaned ? "cleaned" : original ? "original" : null,
  viewer_url: null,
  variants: {
    cleaned: variant("cleaned", cleaned, cleaned ? "c-42" : null),
    original: variant("original", original),
  },
});

const job = (over: Partial<Job>): Job => ({
  id: "job_1",
  name: "j",
  engine: "Instant-NGP",
  status: "waiting",
  progress: 0,
  createdAt: "",
  logs: [],
  outputs: [],
  metrics: [],
  ...over,
});

test("viewer shows the cleaned GLB only when cleanup verified", () => {
  assert.deepEqual(selectViewerMesh(manifest(true)), {
    variant: "cleaned",
    url: "/api/jobs/job_1/exports/cleaned/glb",
    version: "c-42",
  });
  assert.equal(selectViewerMesh(manifest(false))?.variant, "original");
  assert.equal(selectViewerMesh(manifest(false, false)), null);
  assert.equal(selectViewerMesh(null), null);
});

test("a requested variant is honored only if its GLB is available", () => {
  assert.equal(selectViewerMesh(manifest(true), "original")?.variant, "original");
  assert.equal(selectViewerMesh(manifest(false), "cleaned")?.variant, "original");
  assert.deepEqual(viewableVariants(manifest(true)), ["cleaned", "original"]);
  assert.deepEqual(viewableVariants(manifest(false)), ["original"]);
});

test("download links list only verified files", () => {
  const m = manifest(true);
  m.variants.cleaned.formats.obj = file("cleaned", "obj", false);
  assert.deepEqual(downloadLinks(m, "cleaned"), {
    glb: "/api/jobs/job_1/exports/cleaned/glb",
    ply: "/api/jobs/job_1/exports/cleaned/ply",
  });
  assert.deepEqual(downloadLinks(m, null), {});
});

test("jobs with images AND a mesh can open the 3D view", () => {
  const both = job({ imageCount: 100, meshPath: "meshes/r/mesh.glb" });
  assert.equal(effectiveViewerTab(both, "model"), "model");
  assert.equal(effectiveViewerTab(both, "original"), "original");
});

test("tab falls back sensibly when content is missing", () => {
  assert.equal(effectiveViewerTab(job({ imageCount: 5, meshPath: null }), "model"), "original");
  assert.equal(
    effectiveViewerTab(job({ imageCount: 0, meshPath: "m/mesh.glb" }), "masked"),
    "model",
  );
  assert.equal(effectiveViewerTab(null, "original"), "model");
});

test("viewer lists jobs with images or a mesh", () => {
  const jobs = [
    job({ id: "a", imageCount: 3 }),
    job({ id: "b", meshPath: "m/mesh.glb" }),
    job({ id: "c", imageCount: 0, meshPath: null }),
  ];
  assert.deepEqual(
    viewerJobs(jobs).map((j) => j.id),
    ["a", "b"],
  );
});
