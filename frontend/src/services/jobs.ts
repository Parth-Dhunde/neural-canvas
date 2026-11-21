import {
  buildPreviewUrl,
  mapJobFromApi,
  previewFilenameForOriginal,
  type JobApiResponse,
  type JobListApiResponse,
  type UploadApiResponse,
} from "@/lib/mapJob";
import { validateUploadFiles } from "@/lib/uploadLimits";
import { BACKEND_UNREACHABLE_MESSAGE, apiFetch, buildUrl, reportBackendUnreachable } from "./api";
import type { EngineId, Job } from "@/types";

export type JobImageSource = "original" | "masked";

/** POST /api/jobs */
export async function createJob(
  payload: { name?: string; engine: EngineId },
  baseUrl?: string,
): Promise<Job> {
  const data = await apiFetch<JobApiResponse>("/api/jobs", {
    method: "POST",
    baseUrl,
    body: JSON.stringify(payload),
  });
  return mapJobFromApi(data);
}

/** GET /api/jobs */
export async function getJobs(baseUrl?: string): Promise<Job[]> {
  const data = await apiFetch<JobListApiResponse>("/api/jobs", { baseUrl });
  return data.jobs.map(mapJobFromApi);
}

/** GET /api/jobs/{id} */
export async function getJob(id: string, baseUrl?: string): Promise<Job | null> {
  try {
    const data = await apiFetch<JobApiResponse>(`/api/jobs/${id}`, { baseUrl });
    return mapJobFromApi(data);
  } catch {
    return null;
  }
}

export interface JobDeleteOutcome {
  job_id: string;
  status: "deleted" | "not_found" | "refused" | "failed";
  detail: string | null;
}

/** POST /api/jobs/bulk-delete — each job is deleted or refused independently. */
export async function deleteJobs(ids: string[], baseUrl?: string): Promise<JobDeleteOutcome[]> {
  const data = await apiFetch<{ results: JobDeleteOutcome[]; deleted: number }>(
    "/api/jobs/bulk-delete",
    { method: "POST", baseUrl, body: JSON.stringify({ job_ids: ids }) },
  );
  return data.results;
}

/** DELETE /api/jobs/{id} */
export async function deleteJob(id: string, baseUrl?: string): Promise<void> {
  await apiFetch<void>(`/api/jobs/${encodeURIComponent(id)}`, { method: "DELETE", baseUrl });
}

export function filterUploadableFiles(files: File[]): File[] {
  return validateUploadFiles(files).accepted;
}

/** POST /api/jobs/{id}/upload */
export async function uploadImages(
  jobId: string,
  files: File[],
  baseUrl?: string,
  onProgress?: (percent: number) => void,
): Promise<UploadApiResponse> {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", buildUrl(`/api/jobs/${jobId}/upload`, baseUrl));

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as UploadApiResponse);
        return;
      }
      let detail = xhr.responseText;
      try {
        const parsed = JSON.parse(xhr.responseText) as { detail?: string };
        detail = parsed.detail ?? detail;
      } catch {
        // keep raw response
      }
      reject(new Error(detail || `Upload failed: ${xhr.status}`));
    };

    xhr.onerror = () => {
      reportBackendUnreachable();
      reject(new Error(`Upload failed. ${BACKEND_UNREACHABLE_MESSAGE}`));
    };
    xhr.send(form);
  });
}

export function getJobPreviewUrls(job: Job, baseUrl: string): string[] {
  if (!job.imageFilenames?.length) return [];
  return job.imageFilenames.map((filename) =>
    buildPreviewUrl(job.id, previewFilenameForOriginal(filename), baseUrl),
  );
}

export function buildJobImageUrl(
  jobId: string,
  source: JobImageSource,
  filename: string,
  baseUrl: string,
): string {
  const root = baseUrl.replace(/\/$/, "");
  return `${root}/api/jobs/${jobId}/images/${source}/${encodeURIComponent(filename)}`;
}

export function getJobImageUrls(job: Job, baseUrl: string, source: JobImageSource): string[] {
  if (!job.imageFilenames?.length) return [];
  if (source === "original") {
    return job.imageFilenames.map((filename) =>
      buildJobImageUrl(job.id, "original", filename, baseUrl),
    );
  }
  return job.imageFilenames.map((filename) =>
    buildJobImageUrl(job.id, "masked", filename, baseUrl),
  );
}
