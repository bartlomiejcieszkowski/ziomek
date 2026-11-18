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

test("the page does not ask for anything on its own after the first picture", () => {
  // A timer is not something a value test can reach here, so this is read as a string.
  for (const line of part("roster.mjs").split("\n")) {
    if (!line.includes("setInterval(")) continue;
    assert.ok(!line.includes("fetch(") && !line.includes("ask_for("), "the page asks on its own on a timer: " + line);
  }
});

test("the drawing part asks for the rule that moves a number instead of writing its own", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes('from "./clock.mjs"'), "the page part writes its own rule for a number that moves");
  assert.ok(!code.includes("function moving("), "the page part defines the rule again");
});

test("the moment a number was read is kept with it, so the time since reading can be counted", () => {
  assert.ok(body_of("draw_room()").includes("read_at[tile.name] = Date.now()"), "the moment of reading is not kept");
});

test("a number shown after it was read includes the time that passed since reading", () => {
  assert.ok(body_of("held(tile)").includes("moving("), "the shown number is the value as it was read");
});

test("the page keeps a clock so a number that moved is still shown as moved", () => {
  assert.ok(part("roster.mjs").includes("setInterval(keep_current, 1000)"), "nothing on the page keeps it current");
  assert.ok(body_of("keep_current()").includes("held(tile)"), "the number is not shown again from what was read");
});

test("the clock on the page does not ask for anything", () => {
  assert.ok(!body_of("keep_current()").includes("fetch("), "the clock asks for something");
});

test("the part that counts time cannot ask for anything", () => {
  assert.ok(!part("clock.mjs").includes("fetch("), "a part that counts time asks for something");
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

test("the tile shows the line stated for that participant", () => {
  const record = body_of("draw_record()");
  assert.ok(record.includes("show_written_lines()"), "the record is drawn without putting its lines on the tiles");
  const show = body_of("show_written_lines()");
  assert.ok(show.includes("written_by_agent"), "the line stated for a participant is not used");
  assert.ok(show.includes("textContent"), "the tile is not written with the line");
});

test("putting a line on a tile does not ask for anything again", () => {
  assert.ok(!body_of("show_written_lines()").includes("fetch("), "the page asks again for what it already has");
});

test("a window change before anything has been shown is not acted on", () => {
  assert.ok(body_of("lay_out_again()").includes("if (!lastTiles.length) return;"));
});


test("showing or hiding the panel lays the tiles out again", () => {
  // Nothing can be clicked without a browser, so this is read as text like the tests that read how a
  // window change is answered. A size comes from the room measured when the drawing runs, so the
  // change has to be answered after the state of the panel is known, not before it.
  const change = body_of("setShown(shown)");
  assert.ok(change.includes("lay_out_again()"), "the tiles keep the sizes from the last render");
  assert.ok(
    change.indexOf("lay_out_again()") > change.indexOf('classList.toggle("hide", !shown)'),
    "the room is measured before the state of the panel changes",
  );
});

test("the debug page loads its own part before the page is started", () => {
  const html = page("roster_debug.html");
  // What the page asks for is checked by the test that says a page can only be given what a part provides.
  assert.ok(html.indexOf('"/static/roster_debug.mjs"') < html.indexOf("start("), "the page starts before the reading is set");
  assert.ok(!/<script[^>]*>[^<]*(?:function|const state_sizes = null)/.test(html), "the page defines what a part already defines");
});

test("the pages ask for the rule that decides what a moment draws instead of writing their own", () => {
  const drawing = part("roster.mjs");
  const drawing_page = page("renderer.html");
  assert.ok(drawing.includes('from "./frame_order.mjs"'), "the drawing part decides a frame on its own");
  assert.ok(drawing_page.includes('from "/static/frame_order.mjs"'), "the page that draws a skin decides a frame on its own");
  for (const name of ["frame_to_show", "frame_for_view", "moment_to_use", "interval_to_wait"]) {
    assert.ok(!drawing.includes("function " + name + "("), name + " is defined in the drawing part as well");
    assert.ok(!drawing_page.includes("function " + name + "("), name + " is defined in the page as well");
  }
});

test("the picture in a tile is drawn from what the rule says for the moment a participant is at", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes("frame_for_view("), "the tile draws the frame it was given instead of what the moment names");
  assert.ok(code.includes("moment_to_use("), "the moment a participant is at is not asked for");
});

test("a tile is drawn again when its own time has come, without asking the app for anything", () => {
  const code = part("roster.mjs");
  const timers = code.split("\n").filter((line) => line.includes("setInterval(") || line.includes("setTimeout("));
  assert.ok(timers.some((line) => line.includes("draw")), "nothing is drawn again on a timer, so a picture stays as it was first read");
  for (const line of timers) {
    assert.ok(!line.includes("fetch(") && !line.includes("ask_for("), "the page asks on its own on a timer: " + line);
  }
});

test("the page asks for the rule that states what a change carries, instead of reading a message itself", () => {
  const code = part("roster.mjs");
  assert.ok(code.includes("what_a_change_states("), "the page reads what a change carries on its own");
  assert.ok(!code.includes("function what_a_change_states("), "the page defines the rule for what a change states");
});

test("the page keeps the block of a tile so one tile can be drawn again", () => {
  assert.ok(
    part("roster.mjs").includes("block_for_tile[tile.name] = block"),
    "the block of a tile is not kept, so a change cannot be answered for one tile",
  );
});

test("a change of what a participant shows draws that participant's tile from what the page already has", () => {
  const draw = body_of("draw_one_tile(name, expression)");
  assert.ok(draw.includes("lastTiles"), "the tile is drawn from what is asked for again, not from what the page has");
  assert.ok(draw.includes("draw_avatar("), "the tile of the participant the change is for is not drawn");
});

test("answering a change of what a participant shows does not ask for anything again", () => {
  assert.ok(!body_of("draw_one_tile(name, expression)").includes("fetch("), "the page asks again for what it already has");
});

test("nothing is drawn for a participant the page has not seen", () => {
  assert.ok(
    body_of("draw_one_tile(name, expression)").includes("if (!block_for_tile[name]) return;"),
    "a tile the page has not shown is drawn anyway",
  );
});

test("a tile that is not on screen anymore is not drawn into", () => {
  assert.ok(part("roster.mjs").includes("block_for_tile = {}"), "the blocks from the last render are kept, so a change is drawn into a tile that is gone");
});
