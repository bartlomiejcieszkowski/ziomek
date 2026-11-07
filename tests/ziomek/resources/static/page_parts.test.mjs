import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import path from "node:path";

// the tests sit under tests/ in the shape of the code they read, so the source is four levels up
const resources = path.join(import.meta.dirname, "../../../../src/ziomek/resources");

const page = (name) => readFileSync(path.join(resources, name), "utf8").replace(/\r\n/g, "\n");
const part = (name) => readFileSync(path.join(resources, "static", name), "utf8").replace(/\r\n/g, "\n");

test("the part that draws tiles is asked to start, it does not start itself", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes("export async function start("));
  const body = code.replace(/export async function start\([^)]*\) \{/, "");
  assert.ok(!body.includes("start("), "the part starts itself instead of being asked to");
});

test("the page part asks for the counting, the reading of numbers and the shape, and defines none of them itself", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes('from "./roster_grid.mjs"'));
  assert.ok(code.includes('from "./numbers.mjs"'));
  assert.ok(code.includes('from "./state_sizes.mjs"'));
  for (const name of ["count_tracks", "space_left", "whole_frame_grid", "pick_the_biggest", "split_the_blocks", "blocks_in_frames", "read_number", "describe_blocks", "build_report"]) {
    assert.ok(!code.includes("function " + name + "("), name + " is defined here as well");
  }
});

test("the part added in dev mode states values and posts them, defining no shape of its own", () => {
  const code = part("roster_debug.mjs");
  assert.ok(code.includes("state_sizes.report = function ("));
  assert.ok(code.includes('from "./state_sizes.mjs"'), "the values are written in a shape of its own");
  assert.ok(code.includes('fetch(REPORT_PATH, { method: "POST"'), "what was stated is not sent");
  for (const name of ["describe_blocks", "build_report", "read_number"]) {
    assert.ok(!code.includes("function " + name + "("), name + " is defined here as well");
  }
});

test("the debug page loads its own part before the page is started", () => {
  const html = page("roster_debug.html");
  assert.ok(html.includes('<script type="module">import { state_sizes } from "/static/roster_debug.mjs";'));
  assert.ok(html.indexOf('"/static/roster_debug.mjs"') < html.indexOf("start("), "the page starts before the reading is set");
  assert.ok(!/<script[^>]*>[^<]*(?:function|const state_sizes = null)/.test(html), "the page defines what a part already defines");
});
