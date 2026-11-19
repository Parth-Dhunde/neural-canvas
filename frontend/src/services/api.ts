import { DEFAULT_BACKEND_URL } from "@/lib/constants";
import { httpErrorMessage } from "@/lib/httpError";

export function getBaseUrl(): string {
  return DEFAULT_BACKEND_URL;
}

export function buildUrl(path: string, baseUrl = getBaseUrl()): string {
  return `${baseUrl.replace(/\/$/, "")}${path.startsWith("/") ? path : `/${path}`}`;
}

/** Fetch JSON from the backend API. */
export async function apiFetch<T>(
  path: string,
  options: RequestInit & { baseUrl?: string } = {},
): Promise<T> {
  const { baseUrl = getBaseUrl(), headers, ...init } = options;
  const response = await fetch(buildUrl(path, baseUrl), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(httpErrorMessage(body, response.status));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
