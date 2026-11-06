/* the debug part */



const REPORT_PATH = "/api/debug/render";
let last_report = null;
// One block is the whole grid, which the cell part already states, so nothing is added for it.
function describe_blocks() {
  if (stated_blocks.length < 2) return null;  // one block is the whole grid, which the cell part already states
  return stated_blocks;
}
// This is the part that carries what a page measured to the debug path, and it is read only in dev mode,
// where the path that answers is open. A page without it asks for values and nothing states them.
state_sizes = function (path, room, parts, frame, frames) {
  const taken = room.taken ? { padding: room.taken.padding, gap: parts ? { x: room.taken.gap.x * (parts.cols - 1), y: room.taken.gap.y * (parts.rows - 1) } : null } : null;
  const report = {
    path: path,
    measured: room.measured,
    taken: taken,
    room: room,
    // a grid counted in whole frames has no share of the room left over for a cell, so the value it states is the frame itself
    cell: parts ? { width: frame, height: frame } : null,
    frames: frames,
    tile: frame && frames ? frame * frames : null,
    blocks: describe_blocks(),
  };
  const text = JSON.stringify(report);
  if (text === last_report) return;  // the page asks for values on every render, so the same values are not sent again
  last_report = text;
  fetch(REPORT_PATH, { method: "POST", headers: { "Content-Type": "application/json" }, body: text });
};
