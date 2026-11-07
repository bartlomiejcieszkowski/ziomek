import { read_number } from "./numbers.mjs";

// A page cannot state what it measured on its own: the values only exist in the browser. It asks for
// them through this, and a part that a server started with --dev adds is what carries them to the
// debug path. Without that part nothing is stated.
export const state_sizes = { report: null };

// One block is the whole grid, which the values already state, so nothing is added for it.
export function describe_blocks(blocks) {
  if (blocks.length < 2) return null;
  return blocks;
}

// A track is measured from the space left after padding and gaps, and these numbers are read from
// the page rather than written here, since CSS is what sets them.
export function room_for(read_number, root) {
  const styles = getComputedStyle(root);
  const measured = { padding: { x: read_number(styles.paddingLeft), y: read_number(styles.paddingTop) } };
  if (measured.padding.x <= 0 || measured.padding.y <= 0) return { width: 0, height: 0, measured, taken: null };
  return {
    width: root.clientWidth - 2 * measured.padding.x,
    height: root.clientHeight - 2 * measured.padding.y,
    measured,
    taken: { padding: measured.padding, gap: { x: read_number(styles.columnGap), y: read_number(styles.rowGap) } },
  };
}

// The values a page measured are put together here, so the page itself does not hold the shape of a report.
export function build_report(room, path, grid, frame, frames, blocks) {
  const taken = room.taken ? { padding: room.taken.padding, gap: grid ? { x: room.taken.gap.x * (grid.cols - 1), y: room.taken.gap.y * (grid.rows - 1) } : null } : null;
  return {
    path: path,
    measured: room.measured,
    taken: taken,
    room: room,
    // a grid counted in whole frames has no share of the room left over for a cell, so the value it states is the frame itself
    cell: grid ? { width: frame, height: frame } : null,
    frames: frames,
    tile: frame ? { width: frame, height: frame } : null,
    blocks: describe_blocks(blocks),
  };
}
