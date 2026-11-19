/** Shared upload validation helpers (metadata only — no image decoding). */

const ACCEPTED_IMAGE_TYPES = new Set(["image/jpeg", "image/png"]);
const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png"];

export function isSupportedImageFile(file: File): boolean {
  const name = file.name.toLowerCase();
  const byExt = ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
  const byType = file.type ? ACCEPTED_IMAGE_TYPES.has(file.type) : false;
  return byExt || byType;
}
