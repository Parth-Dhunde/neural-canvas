import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import {
  DEFAULT_THEME_PREFERENCE,
  THEME_STORAGE_KEY,
  applyTheme,
  readThemePreference,
  writeThemePreference,
  type ResolvedTheme,
  type ThemePreference,
} from "@/lib/theme";

const listeners = new Set<() => void>();
let current: ThemePreference | null = null;

function getPreference(): ThemePreference {
  if (current === null) current = readThemePreference();
  return current;
}

function notify() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  // Keep tabs in sync when the preference changes in another window.
  const onStorage = (event: StorageEvent) => {
    if (event.key !== THEME_STORAGE_KEY) return;
    current = readThemePreference();
    applyTheme(current);
    notify();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

const THEME_TRANSITION_MS = 260;
let transitionTimer: number | undefined;

export function setThemePreference(preference: ThemePreference) {
  current = preference;
  writeThemePreference(preference);
  // Cross-fade colors only for a user-initiated switch (see .theme-transition in styles.css).
  const root = document.documentElement;
  root.classList.add("theme-transition");
  window.clearTimeout(transitionTimer);
  transitionTimer = window.setTimeout(
    () => root.classList.remove("theme-transition"),
    THEME_TRANSITION_MS,
  );
  applyTheme(preference);
  notify();
}

const noopSubscribe = () => () => {};

/**
 * Current theme preference (Light / Dark / System) and the theme actually shown.
 *
 * `ready` is false during SSR and hydration, when `preference` is only the default; UI that
 * displays the selection should not highlight anything until it is true.
 */
export function useTheme(): {
  preference: ThemePreference;
  resolved: ResolvedTheme;
  ready: boolean;
  setPreference: (preference: ThemePreference) => void;
} {
  const ready = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
  const preference = useSyncExternalStore(subscribe, getPreference, () => DEFAULT_THEME_PREFERENCE);
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    preference === "system" ? "dark" : preference,
  );

  useEffect(() => {
    // Re-apply rather than only resolve: the stored preference may have changed between the
    // pre-paint script and hydration (e.g. in another tab), leaving <html> out of sync.
    setResolved(applyTheme(preference));
    if (preference !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setResolved(applyTheme("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => setThemePreference(next), []);
  return { preference, resolved, ready, setPreference };
}
