import { useEffect } from "react";
import {
  SETTINGS_STORAGE_KEY,
  parseStoredSettings,
  serializeSettings,
} from "@/lib/settingsStorage";
import { DEFAULT_SETTINGS, useAppStore } from "@/store/useAppStore";

/**
 * Load settings saved in this browser once on startup (backend URL, default engine, dense
 * tables, terminal on launch), apply them, and save every later change.
 */
export function usePersistedSettings() {
  useEffect(() => {
    let raw: string | null = null;
    try {
      raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    } catch {
      // Storage blocked (private mode): fall back to defaults for this session.
    }
    const loaded = parseStoredSettings(raw, DEFAULT_SETTINGS);
    const state = useAppStore.getState();
    state.setSettings(loaded);
    state.setSelectedEngine(loaded.defaultEngine);
    state.setTerminal({ open: loaded.terminalOnLaunch });

    let last = serializeSettings(useAppStore.getState().settings);
    return useAppStore.subscribe((next) => {
      const serialized = serializeSettings(next.settings);
      if (serialized === last) return;
      last = serialized;
      try {
        window.localStorage.setItem(SETTINGS_STORAGE_KEY, serialized);
      } catch {
        // Not persisted; the change still applies for this session.
      }
    });
  }, []);
}
