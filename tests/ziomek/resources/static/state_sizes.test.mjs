import assert from "node:assert/strict";
import test from "node:test";

import { blocks_in_frames } from "../../../../src/ziomek/resources/static/roster_grid.mjs";
import { build_report, describe_blocks, state_sizes } from "../../../../src/ziomek/resources/static/state_sizes.mjs";

const room = (width, height, padding, gap) => ({ measured: { width, height }, taken: { padding: { x: padding, y: padding }, gap: { x: gap, y: gap } } });

test("nothing is reported while no reading was set", () => {
  assert.equal(state_sizes.report, null);
  assert.equal(state_sizes.report?.("measured", room(100, 100, 30, 8), null, null, null), undefined);
});

test("a page that sets a reading reports through it", () => {
  const stated = [];
  state_sizes.report = (path, room_seen, grid, frame, frames, blocks) => stated.push(build_report(room_seen, path, grid, frame, frames, blocks));

  state_sizes.report?.("measured", room(2000, 1100, 30, 8), { rows: 10, cols: 20 }, 100, 1, blocks_in_frames({ rows: 10, cols: 20 }, 3, 100));
  assert.equal(stated.length, 1);
});

test("a reader can reproduce a stated number from what the report carries", () => {
  const seen = room(2260, 1311, 30, 8);
  const grid = { rows: 11, cols: 20 };
  const report = build_report(seen, "measured", grid, 100, 1, blocks_in_frames(grid, 2, 100));

  assert.deepEqual(report.measured, { width: 2260, height: 1311 });
  assert.deepEqual(report.taken.padding, { x: 30, y: 30 });
  // gaps sit between tracks, so a grid of one row takes nothing on that axis.
  assert.deepEqual(report.taken.gap, { x: 8 * (grid.cols - 1), y: 8 * (grid.rows - 1) });
});

test("one block is the whole grid, so nothing is stated for it", () => {
  assert.equal(describe_blocks([{ row: 0, col: 0, rows: 2, cols: 3, tile: { width: 300, height: 200 } }]), null);
});

test("each block stated carries the size its own tile was given", () => {
  const blocks = describe_blocks(blocks_in_frames({ rows: 2, cols: 3 }, 4, 100));
  assert.ok(blocks.length >= 2);
  for (const block of blocks) {
    assert.equal(block.tile.width, block.cols * 100);
    assert.equal(block.tile.height, block.rows * 100);
  }
});
