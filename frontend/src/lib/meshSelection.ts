// Pure helpers for choosing which mesh the viewer shows and which downloads are offered.
// Runtime-import free so they can be unit-tested with `node --test`.
import type { ExportManifestApi, MeshFormat, MeshVariant } from "@/services/exports";
import type { Job, ViewerImageSource } from "@/types";

export interface ViewerMesh {
  variant: MeshVariant;
  /** Backend-relative download URL of the GLB. */
  url: string;
  /** Changes whenever the underlying file changes, for cache-busting. */
  version: string;
}

function glbOf(manifest: ExportManifestApi, variant: MeshVariant): ViewerMesh | null {
  const entry = manifest.variants[variant]?.formats.glb;
  if (!entry?.available || !entry.url) return null;
  const version = manifest.variants[variant].cleanup_id ?? String(entry.bytes);
  return { variant, url: entry.url, version };
}

/**
 * Mesh to display. Uses `requested` when that variant's GLB verified, otherwise the backend's
 * preferred variant (cleaned only after a successful, verified cleanup; else the Stage 5 GLB).
 */
export function selectViewerMesh(
  manifest: ExportManifestApi | null,
  requested?: MeshVariant | null,
): ViewerMesh | null {
  if (!manifest) return null;
  if (requested) {
    const chosen = glbOf(manifest, requested);
    if (chosen) return chosen;
  }
  return manifest.preferred ? glbOf(manifest, manifest.preferred) : null;
}

/** Variants whose GLB can be displayed, in display order. */
export function viewableVariants(manifest: ExportManifestApi | null): MeshVariant[] {
  if (!manifest) return [];
  return (["cleaned", "original"] as MeshVariant[]).filter((v) => glbOf(manifest, v) !== null);
}

/** Verified download URLs for one variant. */
export function downloadLinks(
  manifest: ExportManifestApi | null,
  variant: MeshVariant | null,
): Partial<Record<MeshFormat, string>> {
  if (!manifest || !variant) return {};
  const links: Partial<Record<MeshFormat, string>> = {};
  for (const fmt of ["glb", "obj", "ply"] as MeshFormat[]) {
    const entry = manifest.variants[variant]?.formats[fmt];
    if (entry?.available && entry.url) links[fmt] = entry.url;
  }
  return links;
}

/** Jobs the viewer can show: anything with source images or a generated mesh. */
export function viewerJobs(jobs: Job[]): Job[] {
  return jobs.filter((job) => (job.imageCount ?? 0) > 0 || Boolean(job.meshPath));
}

/**
 * Tab actually shown. The 3D view is available for any job with a mesh (images or not);
 * without a mesh, a job with images falls back to its original images.
 */
export function effectiveViewerTab(
  job: Job | null,
  requested: ViewerImageSource,
): ViewerImageSource {
  if (!job) return "model";
  const hasImages = (job.imageCount ?? 0) > 0;
  if (requested === "model" && !job.meshPath && hasImages) return "original";
  if (requested !== "model" && !hasImages) return "model";
  return requested;
}
