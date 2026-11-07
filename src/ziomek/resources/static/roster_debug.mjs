/* the debug part */

import { build_report, state_sizes } from "./state_sizes.mjs";

const REPORT_PATH = "/api/debug/render";
let last = null;

// What a page measured is written in one shape, so the values seen here stay the same as the values read in a browser.
state_sizes.report = function (path, room, grid, frame, frames, blocks) {
  const report = build_report(room, path, grid, frame, frames, blocks);
  if (JSON.stringify(report) === JSON.stringify(last)) return;
  last = report;
  fetch(REPORT_PATH, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(report) });
};
