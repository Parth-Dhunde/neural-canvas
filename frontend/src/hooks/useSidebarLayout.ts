import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_SIDEBAR_PREFS,
  SIDEBAR_DEFAULT_WIDTH,
  applySidebarLayout,
  clampSidebarWidth,
  readSidebarPrefs,
  writeSidebarPrefs,
  type SidebarPrefs,
} from "@/lib/sidebarLayout";

export interface SidebarLayout extends SidebarPrefs {
  /** Live resize (drag): applies immediately; call commit() when the drag ends. */
  resize: (width: number) => void;
  /** Persist the current width. */
  commit: () => void;
  /** Set and persist a width (keyboard resizing, reset). */
  setWidth: (width: number) => void;
  setCollapsed: (collapsed: boolean) => void;
  reset: () => void;
}

/**
 * Desktop sidebar width and collapsed state, persisted in localStorage.
 *
 * The pre-paint SIDEBAR_INIT_SCRIPT has already applied the saved layout to <html>; this hook
 * reads the same preferences after hydration so React state matches what is on screen.
 */
export function useSidebarLayout(): SidebarLayout {
  const [prefs, setPrefs] = useState<SidebarPrefs>(DEFAULT_SIDEBAR_PREFS);
  const prefsRef = useRef(prefs);

  const update = useCallback((next: SidebarPrefs, persist: boolean) => {
    prefsRef.current = next;
    setPrefs(next);
    applySidebarLayout(next);
    if (persist) writeSidebarPrefs(next);
  }, []);

  useEffect(() => {
    update(readSidebarPrefs(), false);
  }, [update]);

  const resize = useCallback(
    (width: number) => update({ ...prefsRef.current, width: clampSidebarWidth(width) }, false),
    [update],
  );
  const commit = useCallback(() => writeSidebarPrefs(prefsRef.current), []);
  const setWidth = useCallback(
    (width: number) => update({ ...prefsRef.current, width: clampSidebarWidth(width) }, true),
    [update],
  );
  const setCollapsed = useCallback(
    (collapsed: boolean) => update({ ...prefsRef.current, collapsed }, true),
    [update],
  );
  const reset = useCallback(
    () => update({ width: SIDEBAR_DEFAULT_WIDTH, collapsed: false }, true),
    [update],
  );

  return { ...prefs, resize, commit, setWidth, setCollapsed, reset };
}
