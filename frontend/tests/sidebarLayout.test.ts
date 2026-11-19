// Sidebar width/collapse rules (run with `npm test`).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  SIDEBAR_DEFAULT_WIDTH,
  SIDEBAR_INIT_SCRIPT,
  SIDEBAR_KEY_STEP,
  SIDEBAR_MAX_WIDTH,
  SIDEBAR_MIN_WIDTH,
  SIDEBAR_RAIL_WIDTH,
  SIDEBAR_STORAGE_KEY,
  clampSidebarWidth,
  parseSidebarPrefs,
  sidebarDisplayWidth,
  sidebarWidthForKey,
} from "../src/lib/sidebarLayout.ts";

test("widths are clamped to the usable range", () => {
  assert.equal(clampSidebarWidth(20), SIDEBAR_MIN_WIDTH);
  assert.equal(clampSidebarWidth(9999), SIDEBAR_MAX_WIDTH);
  assert.equal(clampSidebarWidth(250.6), 251);
  assert.equal(clampSidebarWidth(Number.NaN), SIDEBAR_DEFAULT_WIDTH);
});

test("stored preferences parse safely", () => {
  assert.deepEqual(parseSidebarPrefs(null), { width: SIDEBAR_DEFAULT_WIDTH, collapsed: false });
  assert.deepEqual(parseSidebarPrefs("not json"), {
    width: SIDEBAR_DEFAULT_WIDTH,
    collapsed: false,
  });
  assert.deepEqual(parseSidebarPrefs('{"width": 300, "collapsed": true}'), {
    width: 300,
    collapsed: true,
  });
  assert.deepEqual(parseSidebarPrefs('{"width": 5000, "collapsed": "yes"}'), {
    width: SIDEBAR_MAX_WIDTH,
    collapsed: false,
  });
});

test("collapsed sidebars use the rail width but keep the saved width", () => {
  assert.equal(sidebarDisplayWidth({ width: 300, collapsed: true }), SIDEBAR_RAIL_WIDTH);
  assert.equal(sidebarDisplayWidth({ width: 300, collapsed: false }), 300);
});

test("keyboard resizing steps and bounds", () => {
  assert.equal(sidebarWidthForKey(224, "ArrowRight"), 224 + SIDEBAR_KEY_STEP);
  assert.equal(sidebarWidthForKey(300, "ArrowLeft", true), 300 - SIDEBAR_KEY_STEP * 4);
  assert.equal(sidebarWidthForKey(224, "Home"), SIDEBAR_MIN_WIDTH);
  assert.equal(sidebarWidthForKey(224, "End"), SIDEBAR_MAX_WIDTH);
  assert.equal(sidebarWidthForKey(SIDEBAR_MIN_WIDTH, "ArrowLeft"), SIDEBAR_MIN_WIDTH);
  assert.equal(sidebarWidthForKey(224, "a"), null);
});

test("the pre-paint script uses the same storage key and bounds", () => {
  assert.ok(SIDEBAR_INIT_SCRIPT.includes(JSON.stringify(SIDEBAR_STORAGE_KEY)));
  assert.ok(SIDEBAR_INIT_SCRIPT.includes(String(SIDEBAR_MIN_WIDTH)));
  assert.ok(SIDEBAR_INIT_SCRIPT.includes(String(SIDEBAR_MAX_WIDTH)));
});
