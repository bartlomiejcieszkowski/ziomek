// The script of the page as it is, with two changes, because a mock is opened as a file and cannot
// reach the server: the data comes from a fixture that the page opening this defines, and a face is
// drawn as a flat square in the colour its expression maps to. Nothing else here is different, so a
// mock shows the same room measurement, the same grid, the same text rows and the same record.
// Saving needs the server for Markdown; only JSON can be written from a fixture.
const initial = window.fixture.panel_default;

let lastPayload = {};
let lastBlocks = [];
let rendered = 0;
// A block can grow after it has been drawn, so what the page drew inside the last block is
// kept as well; a run of text from one participant joins the block already on screen.
let shown_block = null;
let shown_lines = 0;

const EXT = { markdown: "md", json: "json" };

function el_class(className) {
  const el = document.createElement("span");
  el.className = className;
  return el;
}

const END_TOLERANCE = 4;

function was_at_the_end() {
  const panel = document.getElementById("panel");
  // A viewer this close to the bottom still counts as being at the end, so a line that
  // arrives while they are reading above it does not pull them down.
  return panel.scrollTop + panel.clientHeight >= panel.scrollHeight - END_TOLERANCE;
}

function follow_to_the_end(follow) {
  const panel = document.getElementById("panel");
  if (follow) panel.scrollTop = panel.scrollHeight;
}

function renderBlock(block) {
  // Each record item is a list item; the panel is a record, so the marker rule and the
  // indent are both taken away. The position is read before the line is added, so a viewer
  // who is above the end keeps reading where they were.
  const follow = was_at_the_end();
  const row = document.createElement("li");
  if (block.kind === "system") {
    // A system line is its own line between the boxes, in the color for quotes.
    const item = document.createElement("p");
    item.className = block.author === "system" ? "system_text" : "event";
    if (block.name) {
      const name = el_class("name");
      name.textContent = block.name;
      item.append(name);
      if (block.author) {
        // The author is kept on the line because the file keeps it too.
        const mark = el_class("group_author");
        mark.textContent = " (" + block.author + ")";
        item.append(mark);
      }
    }
    const text = document.createElement("span");
    text.textContent = block.text;
    item.append(text);
    if (block.assignment) {
      // The voice and the face stand apart from the action, in their own color.
      const drawn = el_class("assignment");
      drawn.textContent = " " + block.assignment;
      item.append(drawn);
    }
    row.append(item);
    document.getElementById("transcript").append(row);
    // A line written by the system is not part of a run, so the block before it is closed.
    shown_block = null;
    shown_lines = 0;
    follow_to_the_end(follow);
    return;
  }

  const box = document.createElement("div");
  box.className = "box";

  const header = document.createElement("div");
  header.append(el_class("name"));           // the name keeps its own element, the box has none
  header.lastChild.textContent = block.name;
  if (block.author) {
    const mark = el_class("group_author");
    // The author stays as text: colors cannot show in a file, so both sides keep it.
    mark.textContent = " (" + block.author + ")";
    header.append(mark);
  }
  box.appendChild(header);

  for (const line of block.lines) {
    const p = document.createElement("p");
    p.textContent = line;
    box.appendChild(p);
  }
  shown_block = box;
  shown_lines = block.lines.length;
  row.append(box);
  document.getElementById("transcript").append(row);
  follow_to_the_end(follow);
}

// Cells come from the space that is actually available, not from a fixed minimum: the
// longer edge is halved first, and a cell is only split when the parts cannot hold
// everyone. A cell is not made smaller than this, so a tile stays readable.


let made_blocks = [];  // the blocks this render made, in position order
let stated_blocks = [];  // each block with the size its own tile was given

// A page cannot state what it measured on its own: the values only exist in the browser. It asks for
// them through this, and a part that a server started with --dev adds is what carries them to the
// debug path. Without that part nothing is stated.
let state_sizes = null;

// A gap belongs to no block and padding is outside the area the grid is given, so a track can only be
// measured from the space left after both. These numbers are read from the page rather than written
// here, since CSS is what sets them, and they are kept so the values a page states can be reproduced.
function measure_room(root) {
  const styles = getComputedStyle(root);
  const read_number = function (value) { return parseFloat(value) || 0; };
  const taken = {
    padding: { x: read_number(styles.paddingLeft) + read_number(styles.paddingRight), y: read_number(styles.paddingTop) + read_number(styles.paddingBottom) },
    gap: { x: read_number(styles.columnGap), y: read_number(styles.rowGap) },
  };
  return {
    measured: { width: root.clientWidth, height: root.clientHeight },
    taken: taken,
    width: root.clientWidth - taken.padding.x,
    height: root.clientHeight - taken.padding.y,
  };
}

// A track costs the frame plus the gap that follows it, so a single row or a single column takes
// nothing: a gap only exists between two tracks. Padding sits outside the area the grid is given, so
// the counts are taken from what is left after both.
function available_room(room, parts) {
  return { width: room.width - room.taken.gap.x * (parts.cols - 1), height: room.height - room.taken.gap.y * (parts.rows - 1) };
}

// Pixels stay even only when a picture is scaled by whole numbers, so a block is a whole number of
// frames on each axis rather than a share of the box. The smallest frame among the skins present is
// used, so every tile on the page is measured the same way.
function largest_tile(tiles) {
  let frame = 0;
  for (const tile of tiles) {
    const skin = tile.avatar && skins[tile.avatar.skin];
    if (!skin || !skin.frameWidth || !skin.frameHeight) continue;
    const side = Math.min(skin.frameWidth, skin.frameHeight);
    if (!frame || side < frame) frame = side;
  }
  return frame;
}

// Space that no frame fits into stays outside the grid instead of becoming bars inside a tile, so the
// grid is counted in whole frames rather than by dividing the box into equal tracks.
function whole_frame_grid(room, frame) {
  const tracks = function (space, gap) { return Math.floor((space + gap) / (frame + gap)); };
  return { rows: tracks(room.height, room.taken.gap.y), cols: tracks(room.width, room.taken.gap.x) };
}

// A block is a whole number of tracks. Splitting the biggest block, along its longer edge, is what brings
// the number of blocks up to the number of participants; half of an odd span is not a block, so a block
// that cannot be split stays as it is.
function pick_the_biggest(blocks) {
  let biggest = null;
  for (const block of blocks.slice().sort(function (a, b) { return a.row - b.row || a.col - b.col; })) {
    if (block.rowSpan < 2 && block.colSpan < 2) continue;  // a single track cannot be split in half
    if (!biggest || block.rowSpan * block.colSpan > biggest.rowSpan * biggest.colSpan) biggest = block;
  }
  return biggest;
}

function split_the_blocks(grid, count) {
  const blocks = [{ row: 0, col: 0, rowSpan: grid.rows, colSpan: grid.cols }];
  while (blocks.length < count) {
    const biggest = pick_the_biggest(blocks);
    if (!biggest) break;  // a span one track wide cannot be halved without breaking a frame count
    if (biggest.rowSpan >= biggest.colSpan) {
      const half = Math.floor(biggest.rowSpan / 2);
      blocks.push({ row: biggest.row + half, col: biggest.col, rowSpan: biggest.rowSpan - half, colSpan: biggest.colSpan });
      biggest.rowSpan = half;
    } else {
      const half = Math.floor(biggest.colSpan / 2);
      blocks.push({ row: biggest.row, col: biggest.col + half, rowSpan: biggest.rowSpan, colSpan: biggest.colSpan - half });
      biggest.colSpan = half;
    }
  }
  return blocks.sort(function (a, b) { return a.row - b.row || a.col - b.col; });
}

// A block is a whole number of frames on each axis, so the size it is given is that count times the frame.
// The same values are used for the tile and for what the page states, so a reader is not shown two numbers.
function blocks_in_frames(grid, count, frame) {
  return split_the_blocks(grid, count).map(function (block) {
    return { row: block.row, col: block.col, rows: block.rowSpan, cols: block.colSpan, tile: { width: block.colSpan * frame, height: block.rowSpan * frame } };
  });
}

function apply_largest_tile(root, room, parts) {
  const frame = largest_tile(parts);
  if (!frame) {  // nothing was read for these skins, so no size can be derived
    stated_blocks = [];
    state_sizes?.("no frame size was read for these skins", room, null, null, null);
    return;
  }
  const grid = whole_frame_grid(room, frame);
  if (!grid.rows || !grid.cols) {
    stated_blocks = [];
    state_sizes?.("no whole frame fits in this room", room, null, frame, null);
    return;
  }
  root.style.gridTemplateColumns = "repeat(" + grid.cols + ", " + frame + "px)";
  root.style.gridTemplateRows = "repeat(" + grid.rows + ", " + frame + "px)";
  stated_blocks = blocks_in_frames(grid, parts.length, frame);
  state_sizes?.("measured", room, grid, frame, 1);
}

function render(tiles) {
  const root = document.getElementById("roster");
  root.innerHTML = "";
  const count = document.getElementById("count");
  count.textContent = tiles.length + " participants";
  const room = measure_room(root);
  if (room.width <= 0 || room.height <= 0) {  // the stacked layout has no room to measure, so nothing here applies
    stated_blocks = [];
    state_sizes?.("cannot be measured", room, null, null, null);
    return;
  }
  apply_largest_tile(root, room, tiles);

  let placed = 0;
  for (const tile of tiles) {
    const place = stated_blocks[placed];
    placed += 1;
    if (!place) continue;  // the room cannot be divided further, so this participant has no block
    const el = document.createElement("div");
    el.className = "tile";
    el.style.gridColumn = (place.col + 1) + " / span " + place.cols;
    el.style.gridRow = (place.row + 1) + " / span " + place.rows;
    el.style.width = place.tile.width + "px";
    el.style.height = place.tile.height + "px";
    const block = el_class("avatar");
    el.appendChild(block);

    const top = el_class("top");
    renderText(top, "name", tile.name);
    renderText(top, "expression", tile.expression);
    el.appendChild(top);

    // The text sits at the bottom of the block; the whole text is in the transcript panel.
    const bottom = el_class("bottom");
    if (textOn()) renderText(bottom, "text", tile.status_text);
    renderText(bottom, "system_text", tile.system_text);
    if (tile.state === "held") {
      const middle = el_class("middle");
      renderText(middle, "on_hold", "on hold\n" + held(tile));
      el.appendChild(middle);
    }
    el.appendChild(bottom);
    root.appendChild(el);
    draw_avatar(tile, block);
  }
}

const skins = {};  // one mapping per skin, so participants that share a skin share one copy

// A mock has no server, so a skin is the mapping the fixture states for it.
async function load_skins(tiles) {
  for (const tile of tiles) {
    const name = tile.avatar && tile.avatar.skin;
    if (!name || skins[name]) continue;
    skins[name] = window.fixture.skins[name];
  }
}

// A picture cannot be read from a page opened as a file, so the block shows a flat square in the
// colour that the fixture states for this expression. The block is still sized by the frame, so the
// room, the grid and the size of a block are the same as on the page.
function draw_avatar(tile, block) {
  const avatar = tile.avatar;
  if (!avatar) return;
  const skin = skins[avatar.skin];
  if (!skin) return;  // nothing was stated for this skin, so the block stays as it is
  block.style.background = (skin.colors && skin.colors[tile.expression]) || "#2a2a30";
}

function held(tile) {
  const seconds = tile.held_seconds || 0;
  return String(Math.floor(seconds / 60)).padStart(2, "0") + ":" + String(seconds % 60).padStart(2, "0");
}

function renderText(root, className, value) {
  const el = document.createElement("div");
  el.className = className;
  el.textContent = value || "";
  // The whole text stays reachable on hover; only the display is cut, and the ellipsis comes from the clamp.
  if (value) el.title = value;
  root.appendChild(el);
}

function pad(n) {
  return String(n).padStart(2, "0");
}

function dateParts(at) {
  return [at.getUTCFullYear(), pad(at.getUTCMonth() + 1), pad(at.getUTCDate())];
}

function clockParts(at) {
  return [pad(at.getUTCHours()), pad(at.getUTCMinutes()), pad(at.getUTCSeconds())];
}

// The header and the name show the same clock, in the forms each of them needs.
function headerStamp(at) {
  return dateParts(at).join("-") + "T" + clockParts(at).join("") + "Z";
}

function nameStamp(at) {
  return dateParts(at).join("-") + "_" + clockParts(at).slice(0, 2).join("");
}

function buildFilename(ext, at) {
  return "ziomek_" + nameStamp(at) + "_transcript." + ext;
}

function jsonFile(entries) {
  return new Blob([JSON.stringify(entries)], { type: "application/json" });
}

function download(content, name) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(content);
  link.download = name;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

function readStored(name) {
  const value = localStorage.getItem(name);
  if (value === null) return null;  // nothing stored -> the config default decides the opening
  return value;
}

function textOn() {
  const stored = readStored("ziomek_text");
  return stored !== "0";  // nothing stored means the text is shown
}

function setStored(name, value) {
  localStorage.setItem(name, value);
}

function panelOpen() {
  const stored = readStored("ziomek_panel");
  if (!stored) return initial === "open";
  return stored === "1";
}

function setShown(shown) {
  document.getElementById("layout").classList.toggle("hide", !shown);
  const label = document.getElementById("toggle");
  label.textContent = shown ? "hide" : "show";
}

function labelTextToggle() {
  document.getElementById("state_text").textContent = textOn() ? "hide text" : "show text";
}

document.getElementById("state_text").addEventListener("click", () => {
  const on = !textOn();
  setStored("ziomek_text", on ? "1" : "0");
  labelTextToggle();
  render(lastTiles);
});

labelTextToggle();

document.getElementById("toggle").addEventListener("click", () => {
  const shown = !document.getElementById("layout").classList.contains("hide");
  setShown(!shown);
  setStored("ziomek_panel", shown ? "1" : "0");
});

document.getElementById("formats").addEventListener("click", () => {
  document.getElementById("menu").classList.toggle("open");
});

function stampOf(at) {
  return [at.getFullYear(), pad(at.getMonth() + 1), pad(at.getDate())].join("-") + "T" + pad(at.getHours()) + pad(at.getMinutes()) + pad(at.getSeconds()) + "Z";
}

async function save(format, at) {
  const ext = EXT[format] || format;
  if (format === "json") {
    download(jsonFile(lastPayload), buildFilename(ext, at));
    return;
  }
  const response = await fetch("/api/roster/transcript/markdown?at=" + encodeURIComponent(headerStamp(at)));
  download(new Blob([await response.text()], { type: "text/markdown" }), buildFilename(ext, at));
}

document.getElementById("save").addEventListener("click", () => {
  const at = new Date();
  save("markdown", at);
});

document.getElementById("menu").addEventListener("click", (event) => {
  const ext = event.target.dataset.format;
  if (!ext) return;
  save(event.target.dataset.format, new Date());
});

// A mock shows one state, so the record is taken from the fixture and there is no polling.
async function refresh() {
  const tiles = window.fixture.tiles;
  await load_skins(tiles);
  render(tiles);
  lastPayload = { blocks: window.fixture.blocks };
  lastBlocks = lastPayload.blocks;

  if (lastBlocks.length < rendered) {
    // The record shrank, which means a new call: the panel starts from nothing.
    document.getElementById("transcript").innerHTML = "";
    shown_block = null;
    shown_lines = 0;
    rendered = 0;
  }
  for (const block of lastBlocks.slice(rendered)) {
    renderBlock(block);
  }

  // The last block can have grown since it was drawn, so the lines that joined it are added to
  // the box that is already on screen rather than starting a new item.
  const last = lastBlocks[rendered - 1];
  if (shown_block && last && last.kind === "group" && last.lines.length > shown_lines) {
    const follow = was_at_the_end();
    for (const line of last.lines.slice(shown_lines)) {
      const p = document.createElement("p");
      p.textContent = line;
      shown_block.append(p);
    }
    shown_lines = last.lines.length;
    follow_to_the_end(follow);  // the position was read before the line was added
  }

  rendered = lastBlocks.length;
}

setShown(panelOpen());
refresh();
