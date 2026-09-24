/**
 * SDL-based gamepad debug window.
 * Creates a small window using @kmamal/sdl (the same SDL instance that
 * gamepad-node uses under the hood) and renders a real-time gamepad
 * visualization with animated buttons, axis bars, and connection status.
 *
 * Run standalone: node debug_tools/gamepad-window.js
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { video } = require('@kmamal/sdl');

// Use gamepad-node for actual gamepad input
const gamepadNode = require('gamepad-node');

// ─── Color palette ──────────────────────────────────────────────────────────

const COLORS = {
  bg:        [22, 22, 32],
  body:      [32, 32, 48],
  bodyInner: [22, 22, 36],
  border:    [55, 55, 75],
  dpad:      [48, 48, 68],
  dpadActive:[70, 70, 95],
  btnOff:    [45, 45, 60],
  text:      [180, 180, 200],
  textDim:   [120, 120, 140],
  ok:        [60, 210, 90],
  warn:      [220, 80, 80],
};

const GP_COLORS = [
  [100, 180, 255],  // blue
  [255, 120, 180],  // pink
  [120, 255, 140],  // green
  [255, 200, 80],   // orange
  [200, 140, 255],  // purple
  [255, 160, 80],   // amber
];

// ─── Low-level pixel drawing ────────────────────────────────────────────────

/**
 * Draw a filled rectangle on a pixel buffer.
 * buf: Uint32Array (32-bit BGRA), w: width, h: height
 */
function fillRect(buf, w, x, y, rw, rh, bgra) {
  for (let py = 0; py < rh; py++) {
    const row = (y + py) * w + x;
    for (let px = 0; px < rw; px++) {
      buf[row + px] = bgra;
    }
  }
}

/**
 * Draw a filled circle (midpoint algorithm).
 */
function fillCircle(buf, w, cx, cy, r, bgra) {
  let x = r, y = 0, d = 3 - 2 * r;
  const addYLine = (cx2, cy2, x2, y2) => {
    for (let dy = -y2; dy <= y2; dy++) {
      const py = cy2 + dy;
      if (py >= 0 && py < buf.length / w) {
        for (let dx = -x2; dx <= x2; dx++) {
          const px = cx2 + dx;
          if (px >= 0 && px < w) buf[py * w + px] = bgra;
        }
      }
    }
  };
  while (x >= y) {
    addYLine(cx + x, cy, y, x);
    addYLine(cx - x, cy, y, x);
    addYLine(cx, cy + x, y, x);
    addYLine(cx, cy - x, y, x);
    if (d <= 0) {
      y++;
      d = d + 4 * y + 6;
    } else {
      y++;
      x--;
      d = d + 4 * (y - x) + 10;
    }
  }
}

/**
 * Draw a hollow circle (outline only).
 */
function strokeCircle(buf, w, cx, cy, r, bgra) {
  let x = r, y = 0, d = 3 - 2 * r;
  while (x >= y) {
    // 8 symmetric points
    const set8 = (ox, oy) => {
      if (ox >= 0 && oy >= 0 && oy < buf.length / w) {
        if (ox < w) buf[oy * w + ox] = bgra;
      }
    };
    set8(cx + x, cy + y); set8(cx - x, cy + y);
    set8(cx + x, cy - y); set8(cx - x, cy - y);
    set8(cx + y, cy + x); set8(cx - y, cy + x);
    set8(cx + y, cy - x); set8(cx - y, cy - x);
    if (d <= 0) { y++; d = d + 4 * y + 6; }
    else { y++; x--; d = d + 4 * (y - x) + 10; }
  }
}

// ─── Gamepad visualization ──────────────────────────────────────────────────

function drawGamepad(buf, w, h, gp, color, pulse, offsetX, offsetY) {
  const ox = offsetX, oy = offsetY;
  const W = 240, HH = 170;  // total widget size
  const cx = ox + W / 2, cy = oy + 80; // center of controller body

  // Controller body background
  fillRect(buf, w, cx - W/2, cy - HH/2, W, HH, mkColor(COLORS.body));
  fillRect(buf, w, cx - W/2 + 3, cy - HH/2 + 3, W - 6, HH - 6, mkColor(COLORS.bodyInner));

  // Body border (top + left light, bottom + right dark)
  fillRect(buf, w, cx - W/2, cy - HH/2, W, 2, mkColor([COLORS.border[0]+20, COLORS.border[1]+20, COLORS.border[2]+20]));
  fillRect(buf, w, cx - W/2, cy - HH/2, 2, HH, mkColor([COLORS.border[0]+15, COLORS.border[1]+15, COLORS.border[2]+15]));
  fillRect(buf, w, cx - W/2, cy + HH/2 - 2, W, 2, mkColor([COLORS.border[0]-15, COLORS.border[1]-15, COLORS.border[2]-15]));
  fillRect(buf, w, cx + W/2 - 2, cy - HH/2, 2, HH, mkColor([COLORS.border[0]-15, COLORS.border[1]-15, COLORS.border[2]-15]));

  const buttons = gp.buttons || [];

  // ── D-Pad (left side) ──────────────────────────────────────────────────────
  const dpadX = cx - 55, dpadY = cy - 15;
  const dpadR = 18;
  // Center
  fillCircle(buf, w, dpadX, dpadY, dpadR, mkColor(COLORS.dpad));
  // Up
  drawDpadBtn(buf, w, dpadX, dpadY - dpadR * 1.6, buttons[12] || null, color);
  // Down
  drawDpadBtn(buf, w, dpadX, dpadY + dpadR * 1.6, buttons[13] || null, color);
  // Left
  drawDpadBtn(buf, w, dpadX - dpadR * 1.6, dpadY, buttons[14] || null, color);
  // Right
  drawDpadBtn(buf, w, dpadX + dpadR * 1.6, dpadY, buttons[15] || null, color);

  // ── Action buttons (right side) ─────────────────────────────────────────────
  const actionR = 30;
  const actionButtons = [
    { idx: 6,  label: 'Y' },  // top
    { idx: 7,  label: 'X' },  // right
    { idx: 4,  label: 'B' },  // bottom
    { idx: 5,  label: 'A' },  // left (actually right of center)
  ];
  const actionAngles = [
    { angle: -Math.PI / 2 },  // top - Y
    { angle: 0 },             // right - X
    { angle: Math.PI },       // bottom - B
    { angle: Math.PI / 2 },   // left - A
  ];
  actionButtons.forEach((btn, i) => {
    const a = actionAngles[i].angle;
    const bx = cx + 55 + Math.cos(a) * actionR;
    const by = cy - 15 + Math.sin(a) * actionR;
    const isPressed = btn.idx < buttons.length && buttons[btn.idx].pressed;
    const glow = isPressed ? (0.4 + 0.6 * Math.min(1, pulse * 3)) : 0;

    fillCircle(buf, w, bx, by, 15, mkColor([
      Math.round(COLORS.btnOff[0] + color[0] * glow),
      Math.round(COLORS.btnOff[1] + color[1] * glow),
      Math.round(COLORS.btnOff[2] + color[2] * glow),
      255,
    ]));
    strokeCircle(buf, w, bx, by, 15, mkColor([80, 80, 110, 255]));

    // Draw button letter
    drawText(buf, w, h, btn.label, bx, by + 5, 9, [255, 255, 255, 200]);
  });

  // ── Shoulder / bumpers ──────────────────────────────────────────────────────
  const sbY = cy - HH/2 - 20;
  const sbLabels = ['LB', 'RB', 'LT', 'RT'];
  const sbBtns = [4, 5, 6, 7];
  for (let i = 0; i < 4; i++) {
    const sbx = cx - 55 + i * 36;
    const isPressed = sbBtns[i] < buttons.length && buttons[sbBtns[i]].pressed;
    const pulseAmt = isPressed ? 40 * Math.min(1, pulse * 3) : 0;
    fillRect(buf, w, sbx - 14, sbY - 8, 28, 16, mkColor([
      Math.round(COLORS.btnOff[0] + pulseAmt),
      Math.round(COLORS.btnOff[1] + pulseAmt * 0.3),
      Math.round(COLORS.btnOff[2] + pulseAmt * 0.5),
      255,
    ]));
    drawText(buf, w, h, sbLabels[i], sbx - 8, sbY - 3, 7, [200, 200, 220, 180]);
  }

  // ── Analog sticks ──────────────────────────────────────────────────────────
  const stickR = 35;
  // Left stick
  const lsx = cx - 50, lsy = cy + 30;
  fillCircle(buf, w, lsx, lsy, stickR, mkColor([28, 28, 42]));
  strokeCircle(buf, w, lsx, lsy, stickR - 2, mkColor([50, 50, 70]));

  if (gp.axes?.length >= 2) {
    const lx = lsx + gp.axes[0] * (stickR - 12);
    const ly = lsy + gp.axes[1] * (stickR - 12);
    fillCircle(buf, w, lx, ly, 13, mkColor([color[0], color[1], color[2], 220]));
  }
  // Stick value text
  if (gp.axes?.length >= 2) {
    drawText(buf, w, h, `L:${gp.axes[0].toFixed(2)}`, lsx - 10, lsy + stickR + 10, 8, COLORS.textDim);
  }

  // Right stick
  const rsx = cx + 50, rsy = cy + 30;
  fillCircle(buf, w, rsx, rsy, stickR, mkColor([28, 28, 42]));
  strokeCircle(buf, w, rsx, rsy, stickR - 2, mkColor([50, 50, 70]));

  if (gp.axes?.length >= 4) {
    const rx = rsx + gp.axes[2] * (stickR - 12);
    const ry = rsy + gp.axes[3] * (stickR - 12);
    fillCircle(buf, w, rx, ry, 13, mkColor([color[0], color[1], color[2], 220]));
  }
  if (gp.axes?.length >= 4) {
    drawText(buf, w, h, `R:${gp.axes[2].toFixed(2)}`, rsx - 10, rsy + stickR + 10, 8, COLORS.textDim);
  }

  // ── Center buttons ──────────────────────────────────────────────────────────
  const centerBtns = [
    { idx: 8,  label: 'S' },  // Select / View
    { idx: 9,  label: 'St' }, // Start / Menu
    { idx: 10, label: 'LS' }, // L3
    { idx: 11, label: 'RS' }, // R3
  ];
  centerBtns.forEach((btn, i) => {
    const bx = cx - 22 + i * 15;
    const by = cy - 38;
    const isPressed = btn.idx < buttons.length && buttons[btn.idx].pressed;
    const pa = isPressed ? 50 : 0;
    fillRect(buf, w, bx - 5, by - 5, 10, 10, mkColor([
      Math.round(COLORS.btnOff[0] + pa),
      Math.round(COLORS.btnOff[1] + pa * 0.5),
      Math.round(COLORS.btnOff[2] + pa * 0.7),
      255,
    ]));
  });

  // ── Gamepad info ────────────────────────────────────────────────────────────
  const isConnected = gp.connected;
  const statusColor = isConnected ? COLORS.ok : COLORS.warn;
  fillCircle(buf, w, cx + W/2 - 12, cy - HH/2 + 12, 5, mkColor([...statusColor, 255]));
  drawText(buf, w, h, isConnected ? 'ONLINE' : 'OFFLINE', cx + W/2 - 60, cy - HH/2 + 10, 8, COLORS.textDim);

  // Gamepad name / index
  drawText(buf, w, h, `GP ${gp.index}: ${gp.id}`, cx - W/2 + 5, cy - HH/2 - 8, 9, color);
  drawText(buf, w, h, `${buttons.length} buttons, ${gp.axes?.length || 0} axes`, cx - W/2 + 5, cy - HH/2 + 20, 7, COLORS.textDim);
}

function drawDpadBtn(buf, w, x, y, btn, color) {
  const isPressed = btn?.pressed || false;
  const glow = isPressed ? (0.3 + 0.7 * Math.min(1, btn.pulse || 0)) : 0;
  fillCircle(buf, w, x, y, 10, mkColor([
    Math.round(COLORS.dpad[0] + (color[0] - COLORS.dpad[0]) * glow),
    Math.round(COLORS.dpad[1] + (color[1] - COLORS.dpad[1]) * glow),
    Math.round(COLORS.dpad[2] + (color[2] - COLORS.dpad[2]) * glow),
    isPressed ? 255 : 200
  ]));
  if (isPressed) {
    strokeCircle(buf, w, x, y, 10, mkColor([255, 255, 255, 100]));
  }
}

// ─── Text rendering (simple bitmap font) ────────────────────────────────────

const FONT = {
  A: [0x7C,0x99,0xA9,0xA9,0xA9,0x7C,0x00,0x00],
  B: [0x78,0xD8,0xB8,0x78,0xD8,0xD8,0x78,0x00],
  C: [0x7C,0x88,0x80,0x80,0x80,0x88,0x7C,0x00],
  D: [0x78,0xD8,0xD8,0xD8,0xD8,0xD8,0x78,0x00],
  E: [0xFC,0x88,0x88,0xF0,0x88,0x88,0x88,0x00],
  F: [0xFC,0x88,0x88,0xF0,0x80,0x80,0x80,0x00],
  G: [0x7C,0x88,0x90,0xB8,0xD8,0x88,0x7C,0x00],
  H: [0x80,0x80,0x80,0xF0,0x80,0x80,0x80,0x00],
  I: [0x7C,0x18,0x18,0x18,0x18,0x18,0x7C,0x00],
  J: [0x3C,0x08,0x08,0x08,0x08,0xD8,0x78,0x00],
  K: [0x80,0x88,0x90,0xE0,0x90,0x88,0x80,0x00],
  L: [0x80,0x80,0x80,0x80,0x80,0x80,0xFC,0x00],
  M: [0x80,0xC0,0xA0,0x90,0x88,0x84,0x80,0x00],
  N: [0x80,0xC0,0xA0,0x90,0x88,0x84,0x80,0x00],
  O: [0x7C,0xC8,0xD0,0xD0,0xD0,0xC8,0x7C,0x00],
  P: [0x78,0xD8,0xD8,0x78,0x80,0x80,0x80,0x00],
  Q: [0x7C,0xC8,0xD0,0xD0,0xD8,0xC8,0x7C,0x60],
  R: [0x78,0xD8,0xD8,0x78,0x88,0x88,0x80,0x00],
  S: [0x7C,0x98,0x80,0x70,0x08,0x08,0x78,0x00],
  T: [0xF8,0x18,0x18,0x18,0x18,0x18,0x18,0x00],
  U: [0x7C,0x04,0x04,0x04,0x04,0x04,0x7C,0x00],
  V: [0x7C,0x04,0x04,0x04,0x04,0x24,0x18,0x00],
  W: [0x7C,0x04,0x04,0x04,0x04,0x04,0x7C,0x00],
  X: [0x80,0x40,0x20,0x18,0x20,0x40,0x80,0x00],
  Y: [0x80,0x40,0x20,0x18,0x18,0x18,0x18,0x00],
  Z: [0xC8,0xD0,0xD8,0xD8,0xF0,0xF0,0x60,0x00],
  '0': [0x7C,0xC8,0xD8,0xF8,0xD8,0xC8,0x7C,0x00],
  '1': [0x38,0x30,0x38,0x38,0x38,0x38,0x7E,0x00],
  '2': [0x7C,0xC8,0x08,0x30,0x60,0xC0,0xFE,0x00],
  '3': [0x7C,0xC8,0x08,0x30,0x08,0xC8,0x7C,0x00],
  '4': [0x18,0x38,0x78,0xD8,0xFE,0x08,0x08,0x00],
  '5': [0x7C,0x80,0x80,0x7C,0x08,0xC8,0x7C,0x00],
  '6': [0x7C,0x80,0x80,0x7C,0xC8,0xC8,0x7C,0x00],
  '7': [0xFE,0x08,0x10,0x20,0x40,0x40,0x40,0x00],
  '8': [0x7C,0xC8,0xC8,0x7C,0xC8,0xC8,0x7C,0x00],
  '9': [0x7C,0xC8,0xC8,0x7C,0x08,0x10,0x7C,0x00],
  '.': [0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00],
  ',': [0x00,0x00,0x00,0x00,0x00,0x18,0x30,0x10,0x00],
  '-': [0x00,0x00,0x00,0xF8,0x00,0x00,0x00,0x00],
  ':': [0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x00],
  ' ': [0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00],
  '%': [0x60,0xC0,0x18,0x30,0x60,0xC0,0x00,0x00],
  '(': [0x18,0x30,0x60,0x60,0x60,0x30,0x18,0x00],
  ')': [0x60,0x30,0x18,0x18,0x18,0x30,0x60,0x00],
  '[': [0x7C,0x40,0x40,0x40,0x40,0x40,0x7C,0x00],
  ']': [0x7C,0x10,0x10,0x10,0x10,0x10,0x7C,0x00],
  't': [0x30,0x30,0x3C,0x30,0x30,0x30,0x7E,0x00],
  'g': [0x7C,0x88,0x88,0x7C,0x88,0x88,0x7C,0x78],
  'd': [0x30,0x20,0x20,0x3C,0x22,0x22,0x3C,0x60],
};

function drawText(buf, w, h, text, tx, ty, fontSize, color) {
  // Simple ASCII bitmap font (5x7 + 1)
  const cw = 6;
  const scale = Math.max(1, Math.floor(fontSize / 7));
  for (let ti = 0; ti < text.length; ti++) {
    const ch2 = text[ti];
    const code = FONT[ch2.toUpperCase()];
    if (!code) continue;
    for (let row = 0; row < 8; row++) {
      const bit = code[row] || 0;
      for (let col = 0; col < 6; col++) {
        if (bit & (0x80 >> col)) {
          for (let sy = 0; sy < scale; sy++) {
            for (let sx = 0; sx < scale; sx++) {
              const px = tx + ti * (cw * scale) + col * scale + sx;
              const py = ty + row * scale + sy;
              if (px >= 0 && px < w && py >= 0 && py < h) {
                buf[py * w + px] = mkColor([color[0], color[1], color[2], color[3] ?? 255]);
              }
            }
          }
        }
      }
    }
  }
}

// ─── Helpers ────────────────────────────────────────────────────────────────

/** Create a 32-bit BGRA color value from RGBA components. */
function mkColor([r, g, b, a = 255]) {
  // Node.js Buffer is little-endian, so BGRA packing:
  return (a << 24) | (b << 16) | (g << 8) | r;
}

// ─── Main loop ──────────────────────────────────────────────────────────────

async function main() {
  console.log('Starting gamepad debug window...');

  // Create debug window
  const win = video.createWindow({
    title: 'Humanize AI — Gamepad Debug',
    width: 500,
    height: 220,
    x: 50,
    y: 50,
    resizable: false,
  });

  console.log(`Window: ${win.width}×${win.height}  (${win.pixelWidth}×${win.pixelHeight} px)`);

  // Pre-allocate buffer
  const buf = new Uint32Array(win.pixelWidth * win.pixelHeight);
  const bgraBuf = Buffer.from(buf.buffer);

  // Initialize gamepad manager
  const manager = new gamepadNode.GamepadManager();
  console.log('GamepadManager created.');

  // Handle window close
  let running = true;
  win.on('close', () => { running = false; });

  // Main render loop
  let frame = 0;
  while (running) {
    // Poll gamepad input only — SDL events are handled automatically by the library
    manager.poll();

    // Get connected gamepads
    const gamepads = manager.getGamepads().filter(Boolean);
    const count = gamepads.length;

    // Update title
    if (frame % 15 === 0) {
      win.setTitle(count > 0
        ? `Humanize AI — Gamepad Debug [${count} connected]`
        : 'Humanize AI — Gamepad Debug [none]'
      );
    }

    // Clear background
    const bgColor = mkColor([...COLORS.bg, 255]);
    for (let i = 0; i < buf.length; i++) buf[i] = bgColor;

    // Draw each gamepad side by side
    const slotW = 250;
    for (let i = 0; i < gamepads.length; i++) {
      const gp = gamepads[i];
      const color = GP_COLORS[i % GP_COLORS.length];
      const ox = i * slotW + (win.pixelWidth - gamepads.length * slotW) / 2;
      drawGamepad(buf, win.pixelWidth, win.pixelHeight, gp, color, 1, ox, 5);
    }

    // No gamepads message
    if (gamepads.length === 0) {
      drawText(buf, win.pixelWidth, win.pixelHeight, 'No gamepads detected', 100, 80, 12, [200, 200, 220, 255]);
      drawText(buf, win.pixelWidth, win.pixelHeight, 'Connect a controller', 130, 105, 9, [140, 140, 160, 200]);
      // Animate blinking cursor
      const blink = Math.sin(frame * 0.08) > 0;
      if (blink) drawText(buf, win.pixelWidth, win.pixelHeight, '█', 240, 103, 9, [140, 140, 160, 200]);
    }

    // Render to window
    win.render(win.pixelWidth, win.pixelHeight, win.pixelWidth * 4, 'bgra8888', bgraBuf);

    frame++;
    await new Promise(r => setTimeout(r, 16)); // ~60 FPS
  }

  win.destroy();
  console.log('Debug window closed.');
}

main().catch(err => {
  console.error('Error:', err.message);
  console.error(err.stack);
  process.exit(1);
});
