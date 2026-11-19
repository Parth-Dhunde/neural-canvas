import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Trash2,
  ArrowDownToLine,
  Terminal as TerminalIcon,
  Check,
  Search,
} from "lucide-react";
import { useAppStore } from "@/store/useAppStore";
import type { LogEntry, LogStreamState } from "@/types";
import { cn } from "@/lib/utils";
import { countAppendedLines, filterLines, formatLinesForCopy } from "@/lib/terminalLog";

export function Terminal({
  open,
  onToggle,
  height,
  onResize,
}: {
  open: boolean;
  onToggle: () => void;
  height: number;
  onResize: (h: number) => void;
}) {
  const lines = useAppStore((s) => s.terminal.lines);
  const autoScroll = useAppStore((s) => s.terminal.autoScroll);
  const searchQuery = useAppStore((s) => s.terminal.searchQuery);
  const setTerminal = useAppStore((s) => s.setTerminal);
  const clearTerminal = useAppStore((s) => s.clearTerminal);
  const logStream = useAppStore((s) => s.logStream);
  const backendStatus = useAppStore((s) => s.backendHealth.status);

  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const [atBottom, setAtBottom] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const [cleared, setCleared] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef(false);
  const atBottomRef = useRef(true);
  const lastLineRef = useRef<LogEntry | undefined>(undefined);

  const scrollToBottom = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
    atBottomRef.current = true;
    setAtBottom(true);
    setUnseen(0);
  }, []);

  const onScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    atBottomRef.current = nearBottom;
    setAtBottom(nearBottom);
    if (nearBottom) setUnseen(0);
  }, []);

  // Follow new output only while the user is already at the bottom; never yank them back
  // down while they are reading older lines.
  useLayoutEffect(() => {
    const added = countAppendedLines(lastLineRef.current, lines);
    lastLineRef.current = lines[lines.length - 1];
    if (lines.length === 0) {
      setUnseen(0);
      return;
    }
    setCleared(false);
    const el = scrollRef.current;
    if (!el) return;
    if (autoScroll && atBottomRef.current) {
      el.scrollTop = el.scrollHeight;
      return;
    }
    if (added > 0) setUnseen((n) => n + added);
    // Content grew under a stationary view (auto-scroll off): re-measure so the
    // "new lines" jump button can appear.
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    atBottomRef.current = nearBottom;
    setAtBottom(nearBottom);
  }, [lines, autoScroll]);

  useEffect(() => {
    if (open) scrollToBottom();
  }, [open, scrollToBottom]);

  useEffect(() => {
    const move = (e: MouseEvent) => {
      if (!dragRef.current) return;
      const h = Math.min(Math.max(window.innerHeight - e.clientY - 24, 120), 520);
      onResize(h);
    };
    const up = () => (dragRef.current = false);
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
    return () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
  }, [onResize]);

  const filteredLines = useMemo(() => filterLines(lines, searchQuery), [lines, searchQuery]);

  const copyVisible = async () => {
    const ok = await copyText(formatLinesForCopy(filteredLines));
    setCopyState(ok ? "copied" : "failed");
    setTimeout(() => setCopyState("idle"), 1600);
  };

  const clearDisplay = () => {
    clearTerminal();
    setCleared(true);
  };

  const counts = useMemo(() => {
    return lines.reduce(
      (acc, l) => {
        acc[l.level] = (acc[l.level] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );
  }, [lines]);

  return (
    <div
      className={cn("hairline-t relative flex shrink-0 flex-col nc-console", !open && "h-8")}
      style={{ height: open ? height : 32 }}
    >
      {open && (
        <div
          onMouseDown={() => (dragRef.current = true)}
          className="absolute left-0 right-0 top-0 h-1 cursor-row-resize hover:bg-selected/40"
        />
      )}

      <div className="flex h-8 shrink-0 items-center gap-2 px-3">
        <button
          onClick={onToggle}
          className="flex items-center gap-1.5 text-[11px] tracking-widest uppercase text-muted-foreground hover:text-ivory"
        >
          <TerminalIcon className="h-3.5 w-3.5" strokeWidth={1.6} />
          Terminal
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
        </button>

        <div className="hairline-l mx-1 h-4" />

        <StreamChip stream={logStream} backendStatus={backendStatus} />

        <div className="hidden items-center gap-3 text-[10px] uppercase tracking-widest text-subtle sm:flex">
          <span>
            <span className="mono text-ivory">{lines.length}</span> lines
          </span>
          <span>
            <span className="text-success">{counts.ok || 0}</span> ok
          </span>
          <span>
            <span className="text-warning">{counts.warn || 0}</span> warn
          </span>
          <span>
            <span className="text-destructive">{counts.error || 0}</span> err
          </span>
        </div>

        <div className="flex-1" />

        {open && (
          <>
            <div className="relative hidden w-48 md:block">
              <Search className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-subtle" />
              <input
                value={searchQuery}
                onChange={(e) => setTerminal({ searchQuery: e.target.value })}
                placeholder="Search logs…"
                aria-label="Search logs"
                className="mono h-6 w-full rounded-sm border border-border bg-surface-2 pl-7 pr-12 text-[11px] text-ivory placeholder:text-subtle focus:border-ring focus:outline-none"
              />
              {searchQuery.trim() && (
                <span className="mono pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-subtle">
                  {filteredLines.length}/{lines.length}
                </span>
              )}
            </div>
            <label className="flex cursor-pointer items-center gap-1.5 text-[10px] uppercase tracking-widest text-subtle hover:text-ivory">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setTerminal({ autoScroll: e.target.checked })}
                className="h-3 w-3 accent-bronze"
              />
              Auto-scroll
            </label>
            <button
              onClick={() => void copyVisible()}
              title={
                copyState === "failed"
                  ? "Copy failed — clipboard unavailable"
                  : searchQuery.trim()
                    ? "Copy matching lines"
                    : "Copy displayed lines"
              }
              aria-label="Copy logs"
              className="grid h-6 w-6 place-items-center rounded-sm hover:bg-surface-2"
            >
              {copyState === "copied" ? (
                <Check className="h-3.5 w-3.5 text-success" strokeWidth={1.6} />
              ) : copyState === "failed" ? (
                <Copy className="h-3.5 w-3.5 text-destructive" strokeWidth={1.6} />
              ) : (
                <Copy className="h-3.5 w-3.5 text-subtle" strokeWidth={1.6} />
              )}
            </button>
            <button
              onClick={clearDisplay}
              title="Clear display (job log history is kept)"
              aria-label="Clear display"
              className="grid h-6 w-6 place-items-center rounded-sm hover:bg-surface-2"
            >
              <Trash2 className="h-3.5 w-3.5 text-subtle" strokeWidth={1.6} />
            </button>
            <button
              onClick={scrollToBottom}
              title="Jump to latest"
              aria-label="Jump to latest"
              className="grid h-6 w-6 place-items-center rounded-sm hover:bg-surface-2"
            >
              <ArrowDownToLine className="h-3.5 w-3.5 text-subtle" strokeWidth={1.6} />
            </button>
          </>
        )}
      </div>

      {open && (
        <div className="relative min-h-0 flex-1">
          <div
            ref={scrollRef}
            onScroll={onScroll}
            role="log"
            aria-label="Pipeline log output"
            className="mono terminal-body h-full select-text overflow-auto px-4 py-2 text-[12px] leading-[1.6]"
          >
            {logStream.truncated && (
              <div className="mb-1 text-[11px] text-subtle">
                Older lines are not shown here; the full history is in the job&apos;s
                logs/pipeline.jsonl.
              </div>
            )}
            {filteredLines.length === 0 ? (
              <TerminalEmpty
                stream={logStream}
                backendStatus={backendStatus}
                searching={searchQuery.trim().length > 0 && lines.length > 0}
                cleared={cleared}
              />
            ) : (
              filteredLines.map((l, i) => (
                <LogLine key={l.seq !== undefined ? `${l.jobId}-${l.seq}` : `ui-${i}`} line={l} />
              ))
            )}
            <div className="flex gap-3 text-muted-foreground">
              <LiveClock />
              <span className="w-10 shrink-0 text-bronze">$</span>
              <span className="text-ivory">
                <span className="nc-live-dot inline-block h-3 w-[7px] translate-y-0.5 bg-bronze" />
              </span>
            </div>
          </div>
          {!atBottom && unseen > 0 && (
            <button
              onClick={scrollToBottom}
              className="mono absolute bottom-3 right-5 flex items-center gap-1.5 rounded-sm border border-border-strong bg-popover px-2.5 py-1 text-[11px] text-ivory shadow-md hover:bg-surface-2"
            >
              <ArrowDownToLine className="h-3 w-3" strokeWidth={1.8} />
              {unseen} new line{unseen === 1 ? "" : "s"}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

const LogLine = memo(function LogLine({ line }: { line: LogEntry }) {
  return (
    <div className="flex gap-3 text-muted-foreground" data-seq={line.seq} data-job={line.jobId}>
      <span className="w-[4.5rem] shrink-0 text-subtle">{line.time}</span>
      <span className={cn("w-10 shrink-0 uppercase", levelColor(line.level))}>{line.level}</span>
      <span className="hidden w-6 shrink-0 text-subtle sm:inline" title="Pipeline stage">
        {line.stageId ? `S${line.stageId}` : ""}
      </span>
      <span
        className={cn(
          "min-w-0 flex-1 whitespace-pre-wrap break-words",
          line.level === "error" && "text-destructive",
          line.level === "warn" && "text-warning",
          line.level === "ok" && "text-success",
          line.level === "info" && "text-foreground/90",
        )}
      >
        {line.msg}
      </span>
    </div>
  );
});

function isOffline(stream: LogStreamState, backendStatus: string): boolean {
  return (
    stream.status === "disconnected" ||
    backendStatus === "disconnected" ||
    backendStatus === "error"
  );
}

function StreamChip({ stream, backendStatus }: { stream: LogStreamState; backendStatus: string }) {
  const disconnected = isOffline(stream, backendStatus);
  const view = disconnected
    ? { label: "Backend offline", dot: "bg-destructive", text: "text-destructive", pulse: false }
    : stream.status === "error"
      ? { label: "Log stream error", dot: "bg-destructive", text: "text-destructive", pulse: false }
      : stream.status === "live"
        ? { label: "Live", dot: "bg-success", text: "text-success", pulse: true }
        : stream.status === "loading"
          ? { label: "Connecting", dot: "bg-warning", text: "text-warning", pulse: true }
          : stream.status === "idle"
            ? { label: "Idle", dot: "bg-subtle", text: "text-muted-foreground", pulse: false }
            : { label: "No job", dot: "bg-subtle", text: "text-muted-foreground", pulse: false };
  return (
    <span
      className={cn(
        "mono flex items-center gap-1.5 rounded-sm border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-widest",
        view.text,
      )}
      title={stream.error ?? undefined}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", view.dot, view.pulse && "nc-live-dot")} />
      {view.label}
      {stream.jobId && <span className="normal-case text-subtle">· {stream.jobId}</span>}
    </span>
  );
}

function TerminalEmpty({
  stream,
  backendStatus,
  searching,
  cleared,
}: {
  stream: LogStreamState;
  backendStatus: string;
  searching: boolean;
  cleared: boolean;
}) {
  let message: string;
  let tone = "text-muted-foreground";
  if (searching) {
    message = "No lines match the search.";
  } else if (cleared && !isOffline(stream, backendStatus) && stream.status !== "error") {
    message =
      "Display cleared. New output will appear here; the job's full log history is kept in logs/pipeline.jsonl.";
  } else if (isOffline(stream, backendStatus)) {
    message = "Backend is unreachable. Logs will resume when the connection returns.";
    tone = "text-destructive";
  } else if (stream.status === "error") {
    message = `Could not load pipeline logs: ${stream.error ?? "unknown error"}`;
    tone = "text-destructive";
  } else if (stream.status === "no-job") {
    message = "No active job. Create or open a job to see its pipeline logs.";
  } else if (stream.status === "loading") {
    message = `Loading logs for ${stream.jobId}…`;
  } else if (stream.status === "live") {
    message = "Pipeline is running. Waiting for output…";
  } else {
    message = `No pipeline output to display for ${stream.jobId}. Start the pipeline to stream logs here.`;
  }
  return <div className={cn("py-1 text-[12px]", tone)}>{message}</div>;
}

function levelColor(level: string) {
  switch (level) {
    case "error":
      return "text-destructive";
    case "warn":
      return "text-warning";
    case "ok":
      return "text-success";
    default:
      return "text-subtle";
  }
}

/** Prompt clock; isolated so its 1 s tick doesn't re-render the log list. */
function LiveClock() {
  const [time, setTime] = useState<string | null>(null);
  useEffect(() => {
    setTime(now());
    const id = window.setInterval(() => setTime(now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return <span className="w-[4.5rem] shrink-0 text-subtle">{time ?? "--:--:--"}</span>;
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    // Clipboard API is unavailable outside secure contexts (e.g. LAN IP over http).
    try {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

function now() {
  const d = new Date();
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
function pad(n: number) {
  return n.toString().padStart(2, "0");
}
