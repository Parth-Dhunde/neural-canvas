// Run with `npm test` (Node's built-in test runner; Node strips the TypeScript types).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  countAppendedLines,
  filterLines,
  formatLinesForCopy,
  logStreamChanged,
  selectUnseenEntries,
} from "../src/lib/terminalLog.ts";
import type { LogEntry, LogStreamState } from "../src/types/index.ts";

const line = (msg: string, level: LogEntry["level"] = "info"): LogEntry => ({
  time: "12:00:00",
  level,
  msg,
});

test("filterLines matches case-insensitively and ignores blank queries", () => {
  const lines = [line("Extracting features"), line("Training 45%"), line("COLMAP ERROR", "error")];
  assert.equal(filterLines(lines, "  "), lines);
  assert.deepEqual(
    filterLines(lines, "colmap").map((l) => l.msg),
    ["COLMAP ERROR"],
  );
  assert.equal(filterLines(lines, "TRAINING").length, 1);
  assert.equal(filterLines(lines, "nothing").length, 0);
});

test("countAppendedLines counts by identity while the buffer grows", () => {
  const a = line("a");
  const b = line("b");
  const c = line("c");
  assert.equal(countAppendedLines(undefined, [a, b]), 2);
  assert.equal(countAppendedLines(b, [a, b, c]), 1);
  assert.equal(countAppendedLines(c, [a, b, c]), 0);
});

test("countAppendedLines still counts once the capped buffer drops old lines", () => {
  // Length stays constant when full: [a,b,c] -> [b,c,d] appended one line.
  const [a, b, c, d] = ["a", "b", "c", "d"].map((m) => line(m));
  assert.equal(countAppendedLines(c, [b, c, d]), 1);
  // Previous tail trimmed away entirely: every visible line is new.
  assert.equal(countAppendedLines(a, [c, d]), 2);
  assert.equal(countAppendedLines(a, []), 0);
});

test("formatLinesForCopy renders time, padded level, and message", () => {
  assert.equal(
    formatLinesForCopy([line("hello"), line("bad", "error")]),
    "[12:00:00] INFO  hello\n[12:00:00] ERROR bad",
  );
});

test("selectUnseenEntries drops re-delivered entries", () => {
  const entries = [{ seq: 4 }, { seq: 5 }, { seq: 6 }];
  assert.deepEqual(selectUnseenEntries(entries, 5), [{ seq: 6 }]);
  assert.deepEqual(selectUnseenEntries(entries, 0), entries);
  assert.deepEqual(selectUnseenEntries(entries, 9), []);
});

test("logStreamChanged detects only real changes", () => {
  const state: LogStreamState = { status: "idle", jobId: "job_1", error: null, truncated: false };
  assert.equal(logStreamChanged(state, { status: "idle", jobId: "job_1" }), false);
  assert.equal(logStreamChanged(state, { status: "live" }), true);
  assert.equal(logStreamChanged(state, { error: "x" }), true);
});

test("httpErrorMessage surfaces FastAPI detail instead of raw JSON", async () => {
  const { httpErrorMessage } = await import("../src/lib/httpError.ts");
  assert.equal(httpErrorMessage('{"detail":"Job not found: job_9"}', 404), "Job not found: job_9");
  assert.equal(
    httpErrorMessage('{"detail":[{"msg":"Input should be a valid integer"},{"msg":"x"}]}', 422),
    "Input should be a valid integer; x",
  );
  assert.equal(httpErrorMessage("", 502), "Request failed: 502");
  assert.equal(httpErrorMessage("Bad Gateway", 502), "Bad Gateway");
  assert.equal(httpErrorMessage('{"other":1}', 500), '{"other":1}');
});
