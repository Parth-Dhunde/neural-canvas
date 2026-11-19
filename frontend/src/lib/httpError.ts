/**
 * Human-readable message for a failed API response. FastAPI errors arrive as JSON
 * (`{"detail": "..."}` or a validation list); show the detail rather than raw JSON.
 */
export function httpErrorMessage(body: string, status: number): string {
  const fallback = `Request failed: ${status}`;
  if (!body.trim()) return fallback;
  try {
    const parsed: unknown = JSON.parse(body);
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      const detail = (parsed as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.trim()) return detail;
      if (Array.isArray(detail) && detail.length > 0) {
        return detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item ? String(item.msg) : String(item),
          )
          .join("; ");
      }
    }
  } catch {
    // Not JSON: fall through to the raw body.
  }
  return body;
}
