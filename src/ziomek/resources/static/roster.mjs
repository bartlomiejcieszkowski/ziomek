import { blocks_in_frames, whole_frame_grid } from "./roster_grid.mjs";
import { read_number } from "./numbers.mjs";
import { room_for, state_sizes } from "./state_sizes.mjs";
import { fit_scale } from "./fit.mjs";
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


let stated_blocks = [];  // each block with the size its own tile was given

// A page cannot state what it measured on its own: the values only exist in the browser. It asks for
// them through this, and a part that a server started with --dev adds is what carries them to the
// debug path. Without that part nothing is stated.

// A track is measured from the space left after padding and gaps, and these numbers are read from
// the page rather than written here, since CSS is what sets them.


// A track costs the frame plus the gap that follows it, so a single row or a single column takes
// nothing: a gap only exists between two tracks. Padding sits outside the area the grid is given, so
// the counts are taken from what is left after both.
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


// A block is a whole number of tracks. Splitting the biggest block, along its longer edge, is what brings
// the number of blocks up to the number of participants; half of an odd span is not a block, so a block
// that cannot be split stays as it is.




// A block is a whole number of frames on each axis, so the size it is given is that count times the frame.
// The same values are used for the tile and for what the page states, so a reader is not shown two numbers.


function apply_largest_tile(root, room, parts) {
  const frame = largest_tile(parts);
  if (!frame) {  // nothing was read for these skins, so no size can be derived
    stated_blocks = [];
    state_sizes.report?.("no frame size was read for these skins", room, null, null, null, []);
    return;
  }
  const grid = whole_frame_grid(room, frame);
  if (!grid.rows || !grid.cols) {
    stated_blocks = [];
    state_sizes.report?.("no whole frame fits in this room", room, null, frame, null, []);
    return;
  }
  root.style.gridTemplateColumns = "repeat(" + grid.cols + ", " + frame + "px)";
  root.style.gridTemplateRows = "repeat(" + grid.rows + ", " + frame + "px)";
  stated_blocks = blocks_in_frames(grid, parts.length, frame);
  state_sizes.report?.("measured", room, grid, frame, 1, stated_blocks);
}

function render(tiles) {
  const root = document.getElementById("roster");
  root.innerHTML = "";
  const count = document.getElementById("count");
  count.textContent = tiles.length + " participants";
  const room = room_for(read_number, root);
  if (room.width <= 0 || room.height <= 0) {  // the stacked layout has no room to measure, so nothing here applies
    stated_blocks = [];
    state_sizes.report?.("cannot be measured", room, null, null, null, []);
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
const images = {};  // bytes by skin name for a sheet, and by skin and file name for a single image

async function load_skins(tiles) {
  for (const tile of tiles) {
    const name = tile.avatar && tile.avatar.skin;
    if (!name || skins[name]) continue;
    const response = await fetch("/api/avatar/sprite?skin=" + encodeURIComponent(name));
    // A skin the page cannot get is left undrawn, so nothing is shown for it.
    if (!response.ok) continue;
    const skin = await response.json();
    skins[name] = skin;
    // A definition of type image has no sheet, so its images are fetched one at a time when drawn.
    if (skin.sprite_b64) images[name] = skin.sprite_b64;
  }
}

// A block is a whole number of frames on each axis, so the picture drawn in it is a whole number of frames
// too. Only this frame's own picture is drawn and the rest of the block stays its own background, which is
// what a definition that does not ask for a fit wants. The picture is placed from its centre, since the
// format has no position field.
const show_cell = function (block, skin, frame, scaleWidth, scaleHeight, boxWidth, boxHeight) {
  block.style.inset = "auto";
  block.style.left = (boxWidth - frame.width * scaleWidth) / 2 + "px";
  block.style.top = (boxHeight - frame.height * scaleHeight) / 2 + "px";
  block.style.width = frame.width * scaleWidth + "px";
  block.style.height = frame.height * scaleHeight + "px";
  const sheet = frame.kind === "cell" ? skin : null;
  block.style.backgroundSize =
    (sheet ? sheet.width * scaleWidth : frame.width * scaleWidth) + "px " + (sheet ? sheet.height * scaleHeight : frame.height * scaleHeight) + "px";
  block.style.backgroundPosition =
    (frame.column ? -frame.column * frame.width * scaleWidth : 0) + "px " + (frame.row ? -frame.row * frame.height * scaleHeight : 0) + "px";
}


// A tile shows one frame of its own skin, which is the frame the mapping resolved for it.
function draw_avatar(tile, block) {
  const avatar = tile.avatar;
  if (!avatar) return;
  const skin = skins[avatar.skin];
  if (!skin) return;  // nothing was fetched for this skin, so the block stays as it is
  const frame = avatar.frame;
  const image = image_for(avatar.skin, frame, () => draw_avatar(tile, block));
  if (!image) return;  // not read yet, so it is drawn once the picture arrives
  const boxWidth = block.getBoundingClientRect().width;
  const boxHeight = block.getBoundingClientRect().height;
  if (!boxWidth || !boxHeight || !frame.width || !frame.height) return;  // not laid out yet, so there is no size to scale to
  // A whole count on each axis is what keeps pixels even. A definition that asks for filling is answered by
  // its own rule, which fills the block; one that does not asks for one whole count for both axes, so the
  // shape of a picture is never changed to fill the space it was given.
  const scale = Math.max(1, Math.min(Math.floor(boxWidth / frame.width), Math.floor(boxHeight / frame.height)));
  if (frame.fit) {
    const [fitWidth, fitHeight] = fit_scale(frame.fit, frame.width, frame.height, boxWidth, boxHeight);
    show_cell(block, skin, frame, fitWidth, fitHeight, boxWidth, boxHeight);
    return;
  }
  // The server answers with a data address, so the page uses it as it is.
  block.style.backgroundImage = "url(" + image + ")";
  show_cell(block, skin, frame, scale, scale, boxWidth, boxHeight);
}

function image_for(skin_name, frame, redraw) {
  const key = frame.kind === "cell" ? skin_name : skin_name + "/" + frame.file;
  if (images[key]) return images[key];
  const url =
    frame.kind === "cell"
      ? "/api/avatar/sprite?skin=" + encodeURIComponent(skin_name)
      : "/api/avatar/image?skin=" + encodeURIComponent(skin_name) + "&file=" + encodeURIComponent(frame.file);
  fetch(url)
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data) return;
      images[key] = data.sprite_b64 || data.image_b64;
      redraw();
    });
  return null;
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

function panelOpen(page_default) {
  const stored = readStored("ziomek_panel");
  if (!stored) return page_default === "open";
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

async function refresh() {
  try {
    const response = await fetch("/api/roster");
    const tiles = await response.json();
    await load_skins(tiles);
    render(tiles);
    const stream = await fetch("/api/roster/transcript");
    lastPayload = await stream.json();
    lastBlocks = lastPayload.blocks;
  } catch {
    return;  // a failed poll keeps the record as it was, so nothing is shown from it
  }

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

// The page decides when the view starts and what it shows first.
export async function start(page_default) {
  setShown(panelOpen(page_default));
  await refresh();
  setInterval(refresh, 1000);
}
