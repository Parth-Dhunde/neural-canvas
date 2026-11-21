/** Save text produced in the browser (e.g. a CSV export) as a file. */
export function downloadTextFile(filename: string, text: string, mimeType = "text/plain"): void {
  const blob = new Blob([text], { type: `${mimeType};charset=utf-8` });
  downloadBlob(filename, blob);
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke after the click has been handled so the download is not cancelled.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
