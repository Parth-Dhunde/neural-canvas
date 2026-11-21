import { DEFAULT_BACKEND_URL } from "@/lib/constants";
import { httpErrorMessage } from "@/lib/httpError";

export function getBaseUrl(): string {
  return DEFAULT_BACKEND_URL;
}

export function buildUrl(path: string, baseUrl = getBaseUrl()): string {
  return `${baseUrl.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

export const BACKEND_UNREACHABLE_MESSAGE =
  "The backend could not be reached, so the request did not complete. It may have gone offline.";

/** The request never got a response (backend offline, network down, CORS failure). */
export class BackendUnreachableError extends Error {
  constructor(message = BACKEND_UNREACHABLE_MESSAGE) {
    super(message);
    this.name = "BackendUnreachableError";
  }
}

const unreachableListeners = new Set<() => void>();

/** Subscribe to "a request could not reach the backend"; used to recheck health at once. */
export function onBackendUnreachable(listener: () => void): () => void {
  unreachableListeners.add(listener);
  return () => unreachableListeners.delete(listener);
}

export function reportBackendUnreachable(): void {
  unreachableListeners.forEach((listener) => listener());
}

/** Fetch JSON from the backend API. */
export async function apiFetch<T>(
  path: string,
  options: RequestInit & { baseUrl?: string } = {},
): Promise<T> {
  const { baseUrl = getBaseUrl(), headers, ...init } = options;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, baseUrl), {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    reportBackendUnreachable();
    throw new BackendUnreachableError();
  }

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(httpErrorMessage(body, response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
