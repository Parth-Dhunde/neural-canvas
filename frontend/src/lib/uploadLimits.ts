/** Client-side upload validation to avoid memory spikes in the browser. */

import { isSupportedImageFile } from "@/lib/uploadValidation";

export const MAX_UPLOAD_FILE_BYTES = 50 * 1024 * 1024;
export const MAX_UPLOAD_FILES = 500;
export const UPLOAD_BATCH_SIZE = 20;

export interface UploadValidationResult {
  accepted: File[];
  warnings: string[];
  error: string | null;
}

export function validateUploadFiles(files: File[]): UploadValidationResult {
  const supported = files.filter(isSupportedImageFile);
  const warnings: string[] = [];

  if (supported.length === 0) {
    return {
      accepted: [],
      warnings,
      error: "No supported images selected (jpg, jpeg, png).",
    };
  }

  if (supported.length < files.length) {
    warnings.push(`Skipped ${files.length - supported.length} unsupported file(s).`);
  }

  const withinSize = supported.filter((file) => file.size <= MAX_UPLOAD_FILE_BYTES);
  if (withinSize.length < supported.length) {
    warnings.push(`Skipped ${supported.length - withinSize.length} file(s) over 50 MB.`);
  }

  if (withinSize.length === 0) {
    return {
      accepted: [],
      warnings,
      error: "All selected images exceed the 50 MB limit.",
    };
  }

  const accepted = withinSize.slice(0, MAX_UPLOAD_FILES);
  if (withinSize.length > MAX_UPLOAD_FILES) {
    warnings.push(`Only the first ${MAX_UPLOAD_FILES} images will be uploaded in this session.`);
  }

  return { accepted, warnings, error: null };
}

export function chunkUploadFiles(files: File[]): File[][] {
  const batches: File[][] = [];
  for (let index = 0; index < files.length; index += UPLOAD_BATCH_SIZE) {
    batches.push(files.slice(index, index + UPLOAD_BATCH_SIZE));
  }
  return batches;
}
