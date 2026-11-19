// Pure helpers for the dashboard terminal and log polling. Kept free of runtime imports so
// they can be unit-tested with `node --test` (see tests/terminalLog.test.ts).
import type { LogEntry, LogStreamState } from "@/types";

/** Lines whose message contains `query` (case-insensitive); all lines for an empty query. */
export function filterLines(lines: LogEntry[], query: string): LogEntry[] {
  const q = query.trim().toLowerCase();
  if (!q) return lines;
  return lines.filter((line) => line.msg.toLowerCase().includes(q));
}

/**
 * Number of lines appended since `previousLast` was the last line.
 *
 * Uses identity rather than length because the buffer is capped: once full, appending
 * drops the oldest lines and the length no longer changes.
 */
export function countAppendedLines(previousLast: LogEntry | undefined, lines: LogEntry[]): number {
  if (lines.length === 0) return 0;
  if (previousLast === undefined) return lines.length;
  const index = lines.lastIndexOf(previousLast);
  if (index === -1) {
    // Previous tail is gone: either trimmed away (all visible lines are new) or cleared.
    return lines.length;
  }
  return lines.length - 1 - index;
}

/** Plain-text rendering used by the terminal's Copy button. */
export function formatLinesForCopy(lines: LogEntry[]): string {
  return lines
    .map((line) => `[${line.time}] ${line.level.toUpperCase().padEnd(5)} ${line.msg}`)
    .join("\n");
}

/** Entries with a sequence number above `lastSeq`, guarding against duplicate delivery. */
export function selectUnseenEntries<T extends { seq: number }>(entries: T[], lastSeq: number): T[] {
  return entries.filter((entry) => entry.seq > lastSeq);
}

/** True when the stream state differs from `next` in any provided field. */
export function logStreamChanged(current: LogStreamState, next: Partial<LogStreamState>): boolean {
  return (Object.keys(next) as (keyof LogStreamState)[]).some((key) => current[key] !== next[key]);
}
