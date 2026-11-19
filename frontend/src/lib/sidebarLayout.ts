// Desktop sidebar width and collapsed state: clamping, persistence and pre-paint application.
// Runtime-import free so the pure helpers can be unit-tested with `node --test`.

export const SIDEBAR_STORAGE_KEY = "nc-sidebar";
export const SIDEBAR_MIN_WIDTH = 184;
export const SIDEBAR_MAX_WIDTH = 360;
export const SIDEBAR_DEFAULT_WIDTH = 224;
/** Width of the collapsed icon rail. */
export const SIDEBAR_RAIL_WIDTH = 60;
/** Keyboard resize step (arrow keys); Shift multiplies it by 4. */
export const SIDEBAR_KEY_STEP = 16;

export interface SidebarPrefs {
  width: number;
  collapsed: boolean;
}

export const DEFAULT_SIDEBAR_PREFS: SidebarPrefs = {
  width: SIDEBAR_DEFAULT_WIDTH,
  collapsed: false,
};

export function clampSidebarWidth(width: number): number {
  if (!Number.isFinite(width)) return SIDEBAR_DEFAULT_WIDTH;
  return Math.round(Math.min(SIDEBAR_MAX_WIDTH, Math.max(SIDEBAR_MIN_WIDTH, width)));
}

/** Parse stored preferences; anything malformed falls back to the defaults. */
export function parseSidebarPrefs(raw: string | null): SidebarPrefs {
  if (!raw) return { ...DEFAULT_SIDEBAR_PREFS };
  try {
    const data = JSON.parse(raw) as Partial<SidebarPrefs>;
    return {
      width: typeof data.width === "number" ? clampSidebarWidth(data.width) : SIDEBAR_DEFAULT_WIDTH,
      collapsed: data.collapsed === true,
    };
  } catch {
    return { ...DEFAULT_SIDEBAR_PREFS };
  }
}

export function readSidebarPrefs(): SidebarPrefs {
  try {
    return parseSidebarPrefs(window.localStorage.getItem(SIDEBAR_STORAGE_KEY));
  } catch {
    return { ...DEFAULT_SIDEBAR_PREFS };
  }
}

export function writeSidebarPrefs(prefs: SidebarPrefs): void {
  try {
    window.localStorage.setItem(
      SIDEBAR_STORAGE_KEY,
      JSON.stringify({ width: clampSidebarWidth(prefs.width), collapsed: prefs.collapsed }),
    );
  } catch {
    // Storage unavailable (private mode): the layout still applies for this session.
  }
}

/** Effective desktop width in px (the rail width when collapsed). */
export function sidebarDisplayWidth(prefs: SidebarPrefs): number {
  return prefs.collapsed ? SIDEBAR_RAIL_WIDTH : clampSidebarWidth(prefs.width);
}

/** Apply to <html>: --nc-sidebar-w drives the width, data-sidebar the rail styling. */
export function applySidebarLayout(prefs: SidebarPrefs): void {
  const root = document.documentElement;
  root.style.setProperty("--nc-sidebar-w", `${sidebarDisplayWidth(prefs)}px`);
  root.dataset.sidebar = prefs.collapsed ? "collapsed" : "expanded";
}

/**
 * Inline script run in <head> before first paint so a saved width or collapsed state shows
 * without a layout jump. Mirrors parseSidebarPrefs/applySidebarLayout.
 */
export const SIDEBAR_INIT_SCRIPT = `(function(){try{var p=JSON.parse(localStorage.getItem(${JSON.stringify(SIDEBAR_STORAGE_KEY)})||"{}"),c=p.collapsed===true,w=typeof p.width==="number"&&isFinite(p.width)?Math.round(Math.min(${SIDEBAR_MAX_WIDTH},Math.max(${SIDEBAR_MIN_WIDTH},p.width))):${SIDEBAR_DEFAULT_WIDTH},e=document.documentElement;e.style.setProperty("--nc-sidebar-w",(c?${SIDEBAR_RAIL_WIDTH}:w)+"px");e.dataset.sidebar=c?"collapsed":"expanded";}catch(x){}})();`;

/** Width after a keyboard resize key, or null when the key is not a resize key. */
export function sidebarWidthForKey(width: number, key: string, shift = false): number | null {
  const step = SIDEBAR_KEY_STEP * (shift ? 4 : 1);
  switch (key) {
    case "ArrowLeft":
      return clampSidebarWidth(width - step);
    case "ArrowRight":
      return clampSidebarWidth(width + step);
    case "Home":
      return SIDEBAR_MIN_WIDTH;
    case "End":
      return SIDEBAR_MAX_WIDTH;
    default:
      return null;
  }
}
