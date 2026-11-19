import { useRef, type KeyboardEvent, type PointerEvent } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  ListChecks,
  History as HistoryIcon,
  GitCompareArrows,
  Boxes,
  Settings as SettingsIcon,
  Cpu,
  BookOpen,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { APP_NAME } from "@/lib/constants";
import { SIDEBAR_MAX_WIDTH, SIDEBAR_MIN_WIDTH, sidebarWidthForKey } from "@/lib/sidebarLayout";
import type { SidebarLayout } from "@/hooks/useSidebarLayout";
import { useAppStore } from "@/store/useAppStore";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/jobs", label: "Jobs", icon: ListChecks },
  { to: "/history", label: "History", icon: HistoryIcon },
  { to: "/compare", label: "Compare", icon: GitCompareArrows },
  { to: "/viewer", label: "Viewer", icon: Boxes },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
  { to: "/guide", label: "Guide", icon: BookOpen },
] as const;

/*
 * Below lg the sidebar is an overlay drawer (mobileOpen). From lg up it is a column whose width
 * comes from --nc-sidebar-w (see lib/sidebarLayout.ts and styles.css); `lg:rail:` classes style
 * the collapsed icon rail. The rail variant only applies from lg, so the drawer is unaffected.
 */
export function Sidebar({
  mobileOpen = false,
  onClose,
  layout,
}: {
  mobileOpen?: boolean;
  onClose?: () => void;
  layout: SidebarLayout;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const jobs = useAppStore((s) => s.jobs);
  const hardware = useAppStore((s) => s.hardware);
  const recentJobs = jobs.slice(0, 3);
  const asideRef = useRef<HTMLElement>(null);

  const onResizeStart = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || layout.collapsed) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    document.documentElement.dataset.sidebarResizing = "";
  };
  const onResizeMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    const left = asideRef.current?.getBoundingClientRect().left ?? 0;
    layout.resize(event.clientX - left);
  };
  const onResizeEnd = (event: PointerEvent<HTMLDivElement>) => {
    if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    delete document.documentElement.dataset.sidebarResizing;
    layout.commit();
  };
  const onResizeKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      layout.setCollapsed(!layout.collapsed);
      return;
    }
    const next = sidebarWidthForKey(layout.width, event.key, event.shiftKey);
    if (next === null) return;
    event.preventDefault();
    layout.setWidth(next);
  };

  return (
    <>
      <div
        aria-hidden
        onClick={onClose}
        className={cn(
          "absolute inset-0 z-30 bg-background/70 backdrop-blur-[2px] transition-opacity lg:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <aside
        id="app-navigation"
        ref={asideRef}
        aria-label="Main navigation"
        className={cn(
          "hairline-r nc-sidebar z-40 flex w-[240px] shrink-0 flex-col overflow-hidden transition-transform duration-200",
          "absolute inset-y-0 left-0 lg:relative lg:translate-x-0 lg:overflow-visible",
          mobileOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full",
        )}
      >
        <div className="hairline-b flex h-12 shrink-0 items-center gap-2.5 overflow-hidden px-4 lg:rail:justify-center lg:rail:px-0">
          <BrandMark />
          <div className="flex min-w-0 flex-col leading-none lg:rail:hidden">
            <span className="mono truncate text-[13px] font-semibold tracking-tight text-ivory">
              {APP_NAME}
            </span>
            <span className="label-caps mt-1">Workstation</span>
          </div>
        </div>

        <nav className="flex-1 overflow-x-hidden overflow-y-auto p-2">
          <div className="label-caps mb-2 px-2 pt-2 lg:rail:hidden">Workspace</div>
          <ul className="space-y-0.5">
            {nav.map((item) => {
              const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
              const Icon = item.icon;
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    aria-current={active ? "page" : undefined}
                    title={item.label}
                    className={cn(
                      "group relative flex items-center gap-3 rounded-sm px-2.5 py-2 text-[13px] transition-colors lg:rail:justify-center lg:rail:px-0",
                      active
                        ? "nc-nav-active"
                        : "text-muted-foreground hover:bg-surface-2 hover:text-foreground",
                    )}
                  >
                    {active && (
                      <span className="absolute top-1.5 bottom-1.5 left-0 w-[2px] rounded-full bg-selected" />
                    )}
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        active ? "text-selected" : "text-subtle group-hover:text-foreground",
                      )}
                      strokeWidth={1.6}
                    />
                    <span className="flex-1 truncate lg:rail:sr-only">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>

          <div className="lg:rail:hidden">
            <div className="label-caps mt-6 mb-2 px-2">Recent</div>
            {recentJobs.length === 0 ? (
              <p className="px-2 text-[11px] text-muted-foreground">No recent jobs</p>
            ) : (
              <ul className="space-y-0.5 px-1">
                {recentJobs.map((job) => (
                  <li
                    key={job.id}
                    className="flex items-center gap-2 rounded-sm px-1.5 py-1.5 text-[12px] text-muted-foreground hover:bg-surface-2 hover:text-foreground"
                  >
                    <span
                      className={cn(
                        "mono w-8 shrink-0 text-[10px]",
                        job.status === "running"
                          ? "text-selected"
                          : job.status === "completed"
                            ? "text-success"
                            : job.status === "failed"
                              ? "text-destructive"
                              : "text-subtle",
                      )}
                    >
                      {job.status === "running"
                        ? "RUN"
                        : job.status === "completed"
                          ? "OK"
                          : job.status === "failed"
                            ? "ERR"
                            : "—"}
                    </span>
                    <span className="truncate">{job.name}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </nav>

        <div className="hairline-t space-y-2 p-3 lg:rail:px-2">
          <div
            className="nc-tile nc-chrome flex items-center gap-2 rounded-sm border border-border p-2.5 lg:rail:justify-center lg:rail:p-2"
            title={`${hardware.gpu} · ${hardware.status}`}
          >
            <Cpu className="h-4 w-4 shrink-0 text-bronze" strokeWidth={1.6} />
            <div className="min-w-0 flex-1 lg:rail:hidden">
              <div className="mono truncate text-[11px] text-ivory">{hardware.gpu}</div>
              <div className="mt-1 truncate text-[10px] text-subtle">{hardware.status}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => layout.setCollapsed(!layout.collapsed)}
            aria-label={layout.collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!layout.collapsed}
            aria-controls="app-navigation"
            title={layout.collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden w-full items-center gap-2 rounded-sm px-2 py-1.5 text-[11px] tracking-widest text-subtle uppercase transition-colors hover:bg-surface-2 hover:text-ivory lg:flex lg:rail:justify-center lg:rail:px-0"
          >
            {layout.collapsed ? (
              <PanelLeftOpen className="h-4 w-4 shrink-0" strokeWidth={1.6} />
            ) : (
              <PanelLeftClose className="h-4 w-4 shrink-0" strokeWidth={1.6} />
            )}
            <span className="lg:rail:sr-only">Collapse</span>
          </button>
        </div>

        {/* Resize handle (desktop, expanded only). */}
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize sidebar"
          aria-controls="app-navigation"
          aria-valuemin={SIDEBAR_MIN_WIDTH}
          aria-valuemax={SIDEBAR_MAX_WIDTH}
          aria-valuenow={layout.width}
          aria-valuetext={`${layout.width} pixels wide`}
          tabIndex={layout.collapsed ? -1 : 0}
          title="Drag to resize · double-click to reset · arrow keys to adjust"
          onPointerDown={onResizeStart}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeEnd}
          onPointerCancel={onResizeEnd}
          onDoubleClick={layout.reset}
          onKeyDown={onResizeKey}
          className="group absolute inset-y-0 -right-[3px] z-10 hidden w-[6px] cursor-col-resize touch-none outline-none lg:block lg:rail:hidden"
        >
          <span className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-transparent transition-colors group-hover:bg-selected/60 group-focus-visible:bg-selected group-active:bg-selected" />
        </div>
      </aside>
    </>
  );
}

function BrandMark() {
  return (
    <div className="relative grid h-8 w-8 shrink-0 place-items-center rounded-[6px] border border-border-strong nc-tile shadow-[0_1px_0_oklch(1_0_0/0.06)_inset]">
      <svg viewBox="0 0 24 24" className="h-4 w-4 text-bronze" fill="none" aria-hidden>
        <path d="M4 6l8-3 8 3v12l-8 3-8-3V6z" stroke="currentColor" strokeWidth="1.4" />
        <path d="M4 6l8 3 8-3M12 9v12" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    </div>
  );
}
