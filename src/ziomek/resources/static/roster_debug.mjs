/* the debug part */

import { build_report, state_sizes } from "./state_sizes.mjs";

const REPORT_PATH = "/api/debug/render";
let last = null;

// Only this part can know how the app was started, so it is what says so on screen. What is printed is
// the same report that is sent, so what a reader sees and what was stored cannot disagree.
const indicator = document.createElement("div");
indicator.className = "debug_mode";
indicator.textContent = "debug mode";
const values = document.createElement("div");
values.className = "debug_values";
document.body.append(indicator, values);

// An empty box leaves a reader guessing, so the first line printed is the reason a measurement was not possible.
function describe(report) {
  const lines = [report.path];
  if (report.room) lines.push(`room ${report.room.measured.width}x${report.room.measured.height}`);
  if (report.tile) lines.push(`frame ${report.tile.width}x${report.tile.height}`);
  lines.push(`blocks ${report.blocks ? report.blocks.length : 0}`);
  return lines.join("\n");
}

// What a page measured is written in one shape, so the values seen here stay the same as the values read in a browser.
state_sizes.report = function (path, room, grid, frame, frames, blocks) {
  const report = build_report(room, path, grid, frame, frames, blocks);
  if (JSON.stringify(report) === JSON.stringify(last)) return;
  last = report;
  values.textContent = describe(report);
  fetch(REPORT_PATH, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(report) });
};
