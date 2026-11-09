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

test("a part asks for what it uses, and not for what it does not", () => {
  const code = part("roster.mjs");
  const imports = code.split("\n").filter((line) => line.startsWith("import {"));
  assert.ok(imports.length > 0, "the part asks for nothing");
  const body = code.split("\n").filter((line) => !line.startsWith("import {")).join("\n");
  for (const line of imports) {
    for (const name of line.slice(line.indexOf("{") + 1, line.indexOf("}")).split(",").map((entry) => entry.trim())) {
      assert.ok(body.includes(name), name + " is asked for but not used");
    }
  }
});

test("the pages ask for the rule that decides the size of a skin instead of writing their own", () => {
  assert.ok(part("roster.mjs").includes('from "./fit.mjs"'));
  assert.ok(!part("roster.mjs").includes("function fit_scale("), "the page part writes the rule again");
  const drawing_page = page("renderer.html");
  assert.ok(drawing_page.includes('import { fit_scale } from "/static/fit.mjs"'), "the drawing page does not ask for the rule");
  assert.ok(!drawing_page.includes("function fitScale("), "the drawing page writes the rule again");
});

test("a page that loads a part which asks for another part reads it in a way that allows asking", () => {
  for (const name of ["roster.html", "renderer.html"]) {
    const tags = page(name).match(/<script[^>]*>/g) ?? [];
    assert.ok(tags.length > 0, name + " loads no part at all");
    for (const tag of tags) {
      assert.ok(tag.includes('type="module"'), name + " reads a part in a way that cannot ask: " + tag);
    }
  }
});

test("the page asks for the rule that decides what to ask for", () => {
  // Which part a page is asked for is checked as a value in the test that reads the page as values.
  // Only the fact that it asks for the rule instead of writing one cannot be checked as a value.
  assert.ok(part("roster.mjs").includes('from "./signal.mjs"'), "the page part decides what to ask for on its own");
});

test("the page asks for the whole picture when its connection is open again", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes("signal.onopen"), "nothing is asked when a connection is opened");
  assert.ok(
    code.slice(code.indexOf("signal.onopen")).includes("ask_for(what_to_ask_on_connection())"),
    "a change made while the page was away is not asked for",
  );
});

test("the page does not ask on its own after the first picture", () => {
  // A timer is not something a value test can reach here, so this is read as a string.
  assert.ok(!part("roster.mjs").includes("setInterval("), "the page still asks on a timer");
});

test("a page that cannot keep the connection asks again on its own", () => {
  // How long it waits is checked as a value in the test that reads the page as values. Here only the
  // scheduling can be read, since nothing can be connected without a browser.
  const code = part("roster.mjs");
  assert.ok(code.includes("signal.onclose"), "a lost connection is not connected again");
  assert.ok(
    code.slice(code.indexOf("signal.onclose")).includes("setTimeout(connect_to_signal, AGAIN_AFTER)"),
    "the wait before asking again is left to the browser default",
  );
});

test("the debug page loads its own part before the page is started", () => {
  const html = page("roster_debug.html");
  // What the page asks for is checked by the test that says a page can only be given what a part provides.
  assert.ok(html.indexOf('"/static/roster_debug.mjs"') < html.indexOf("start("), "the page starts before the reading is set");
  assert.ok(!/<script[^>]*>[^<]*(?:function|const state_sizes = null)/.test(html), "the page defines what a part already defines");
});
