import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/lib/utils";
import type { ThemePreference } from "@/lib/theme";

const OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light theme", icon: Sun },
  { value: "dark", label: "Dark theme", icon: Moon },
  { value: "system", label: "Follow system theme", icon: Monitor },
];

/** Compact Light / Dark / System switcher for the top bar. */
export function ThemeSwitcher() {
  const { preference, ready, setPreference } = useTheme();
  return (
    <div
      role="radiogroup"
      aria-label="Theme"
      className="flex items-center gap-0.5 rounded-sm border border-border bg-surface-2 p-0.5"
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          role="radio"
          aria-checked={ready && preference === value}
          aria-label={label}
          title={label}
          onClick={() => setPreference(value)}
          className={cn(
            "grid h-6 w-6 place-items-center rounded-sm transition-colors",
            ready && preference === value
              ? "bg-surface text-selected shadow-sm ring-1 ring-selected/45"
              : "text-subtle hover:text-ivory",
          )}
        >
          <Icon className="h-3.5 w-3.5" strokeWidth={1.7} />
        </button>
      ))}
    </div>
  );
}
