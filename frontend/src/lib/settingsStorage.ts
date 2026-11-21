// Browser-persisted settings. Runtime-import free so it can be unit-tested with node --test.
import type { AppSettings } from "@/types";

export const SETTINGS_STORAGE_KEY = "nc-settings";

/** A backend URL must be an absolute http(s) URL without credentials, query or fragment. */
export function normalizeBackendUrl(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  if (url.username || url.password || url.search || url.hash) return null;
  return `${url.origin}${url.pathname}`.replace(/\/+$/, "");
}

/** Merge stored values over the defaults, ignoring anything malformed. */
export function parseStoredSettings(raw: string | null, defaults: AppSettings): AppSettings {
  if (!raw) return defaults;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return defaults;
  }
  if (!data || typeof data !== "object") return defaults;
  const stored = data as Record<string, unknown>;
  const next: AppSettings = { ...defaults };
  if (typeof stored.backendUrl === "string") {
    next.backendUrl = normalizeBackendUrl(stored.backendUrl) ?? defaults.backendUrl;
  }
  if (typeof stored.denseTables === "boolean") next.denseTables = stored.denseTables;
  if (typeof stored.terminalOnLaunch === "boolean") next.terminalOnLaunch = stored.terminalOnLaunch;
  // Only engines that can run are valid defaults (see lib/engines.ts).
  if (stored.defaultEngine === "Instant-NGP") next.defaultEngine = stored.defaultEngine;
  return next;
}

export function serializeSettings(settings: AppSettings): string {
  const { backendUrl, denseTables, terminalOnLaunch, defaultEngine } = settings;
  return JSON.stringify({ backendUrl, denseTables, terminalOnLaunch, defaultEngine });
}
