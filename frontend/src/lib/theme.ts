export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "nc-theme";
/** NeuralCanvas has always shipped dark; keep that for users who never picked a theme. */
export const DEFAULT_THEME_PREFERENCE: ThemePreference = "dark";

function isPreference(value: unknown): value is ThemePreference {
  return value === "light" || value === "dark" || value === "system";
}

export function readThemePreference(): ThemePreference {
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(stored) ? stored : DEFAULT_THEME_PREFERENCE;
  } catch {
    return DEFAULT_THEME_PREFERENCE;
  }
}

export function writeThemePreference(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Storage unavailable (private mode): the choice still applies for this session.
  }
}

export function systemPrefersDark(): boolean {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return true;
  }
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference === "system") return systemPrefersDark() ? "dark" : "light";
  return preference;
}

/** Apply the theme classes on <html>; tokens in styles.css switch on `.light` / `.dark`. */
export function applyTheme(preference: ThemePreference): ResolvedTheme {
  const resolved = resolveTheme(preference);
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.classList.toggle("light", resolved === "light");
  root.style.colorScheme = resolved;
  root.dataset.themePreference = preference;
  return resolved;
}

/**
 * Inline script run in <head> before first paint, so the stored theme is applied before
 * any content renders (no flash of the wrong theme). Mirrors readThemePreference/applyTheme.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var k=${JSON.stringify(THEME_STORAGE_KEY)},d=${JSON.stringify(DEFAULT_THEME_PREFERENCE)},p=localStorage.getItem(k);if(p!=="light"&&p!=="dark"&&p!=="system")p=d;var r=p==="system"?(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"):p,e=document.documentElement;e.classList.toggle("dark",r==="dark");e.classList.toggle("light",r==="light");e.style.colorScheme=r;e.dataset.themePreference=p;}catch(x){document.documentElement.classList.add("dark");}})();`;
