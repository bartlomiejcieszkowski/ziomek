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

test("the page asks for the rule that reads a message", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes('import { read_signal') && code.includes("read_signal(event.data)"), "the page does not ask for the rule that reads a message");
});

test("the page does not read a message on its own", () => {
  assert.ok(!part("roster.mjs").includes("JSON.parse("), "the page reads a message on its own");
});

// The part that connects is read as one block, so a check about what happens when a connection is
// opened cannot be satisfied by code placed in the handler for a lost connection.
const connection_handler = () => {
  const code = part("roster.mjs");
  const start = code.indexOf("function connect_to_signal() {");
  assert.ok(start >= 0, "the part does not connect on its own");
  return code.slice(start, code.indexOf("\n}", start));
};

test("the page asks for the whole picture when a connection is opened", () => {
  assert.ok(
    connection_handler().includes("signal.onopen = () => ask_for(what_to_ask_on_connection());"),
    "the whole picture is not asked for when a connection is opened",
  );
});

test("the page does not ask on its own after the first picture", () => {
  // A timer is not something a value test can reach here, so this is read as a string.
  assert.ok(!part("roster.mjs").includes("setInterval("), "the page still asks on a timer");
});

test("a page that cannot keep the connection asks again on its own", () => {
  // How long it waits is checked as a value in the test that reads the page as values. Here only the
  // scheduling can be read, since nothing can be connected without a browser.
  assert.ok(
    connection_handler().includes("signal.onclose = () => setTimeout(connect_to_signal, AGAIN_AFTER);"),
    "a lost connection is not connected again on its own",
  );
});

const body_of = (definition) => {
  const code = part("roster.mjs");
  const start = code.indexOf(`function ${definition} {`);
  assert.ok(start >= 0, `the page does not have ${definition}`);
  return code.slice(start, code.indexOf("\n}", start));
};

test("the page lays out the picture again when the window it is in changes size", () => {
  // A window is not something the app knows about, so this can only be read as text.
  assert.ok(part("roster.mjs").includes('window.addEventListener("resize", lay_out_again)'));
  assert.ok(body_of("lay_out_again()").includes("render(lastTiles)"));
});

test("a window change is answered without asking for the picture again", () => {
  assert.ok(!body_of("lay_out_again()").includes("fetch("), "the page asks again for what it already has");
});

test("the page keeps what it showed so a window change can be answered from it", () => {
  assert.ok(body_of("render(tiles)").includes("lastTiles = tiles;"), "nothing is kept from what was shown");
});

test("a window change before anything has been shown is not acted on", () => {
  assert.ok(body_of("lay_out_again()").includes("if (!lastTiles.length) return;"));
});

test("the debug page loads its own part before the page is started", () => {
  const html = page("roster_debug.html");
  // What the page asks for is checked by the test that says a page can only be given what a part provides.
  assert.ok(html.indexOf('"/static/roster_debug.mjs"') < html.indexOf("start("), "the page starts before the reading is set");
  assert.ok(!/<script[^>]*>[^<]*(?:function|const state_sizes = null)/.test(html), "the page defines what a part already defines");
});
