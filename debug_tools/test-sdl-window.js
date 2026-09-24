/**
 * Quick test: Create an SDL window and see what's possible.
 */
import { createRequire } from 'module';
const require = createRequire(import.meta.url);

// Import the same SDL instance that gamepad-node uses
const { video, controller, keyboard, mouse } = require('@kmamal/sdl');

console.log('Testing SDL window creation...');
console.log('video methods:', Object.keys(video));

try {
  // Create a small debug window
  const win = video.createWindow({
    title: 'SDL Test - Humanize AI',
    width: 400,
    height: 300,
    x: 100,
    y: 100,
    resizable: false,
  });

  console.log(`Window created successfully!`);
  console.log(`  Size: ${win.width}x${win.height}`);
  console.log(`  Pixel size: ${win.pixelWidth}x${win.pixelHeight}`);
  console.log(`  Window methods:`, Object.getOwnPropertyNames(Object.getPrototypeOf(win)).filter(m => !m.startsWith('_')));

  // Test clearing the window with a color
  const buffer = Buffer.allocUnsafe(win.pixelWidth * win.pixelHeight * 4);
  for (let i = 0; i < win.pixelWidth * win.pixelHeight; i++) {
    buffer[i * 4] = 30;     // R
    buffer[i * 4 + 1] = 30; // G
    buffer[i * 4 + 2] = 50; // B
    buffer[i * 4 + 3] = 255; // A
  }

  // Draw a small colored square (center)
  const cx = Math.floor(win.pixelWidth / 2);
  const cy = Math.floor(win.pixelHeight / 2);
  for (let dy = -10; dy <= 10; dy++) {
    for (let dx = -10; dx <= 10; dx++) {
      const px = cx + dx;
      const py = cy + dy;
      if (px >= 0 && px < win.pixelWidth && py >= 0 && py < win.pixelHeight) {
        buffer[(py * win.pixelWidth + px) * 4] = 255;
        buffer[(py * win.pixelWidth + px) * 4 + 1] = 100;
        buffer[(py * win.pixelWidth + px) * 4 + 2] = 100;
        buffer[(py * win.pixelWidth + px) * 4 + 3] = 255;
      }
    }
  }

  // Render the buffer to the window (format must be lowercase)
  win.render(win.pixelWidth, win.pixelHeight, win.pixelWidth * 4, 'bgra8888', buffer);
  console.log('Buffer rendered to window!');

  // Check available keys
  if (controller.getGamepads().length > 0) {
    console.log(`Found ${controller.getGamepads().length} gamepad(s)`);
  }

  console.log('\nWindow is visible. Close it to exit...');

  // Main loop - keep window alive and responsive
  let frame = 0;
  let running = true;

  win.on('close', () => { running = false; });

  while (running) {
    // Poll events from all systems
    video.poll();
    controller.poll();
    keyboard?.poll();
    mouse?.poll();

    // Animate the center square
    const buffer = Buffer.allocUnsafe(win.pixelWidth * win.pixelHeight * 4);
    const time = frame * 0.05;
    const radius = 10 + Math.sin(time) * 5;

    for (let py = 0; py < win.pixelHeight; py++) {
      for (let px = 0; px < win.pixelWidth; px++) {
        const idx = (py * win.pixelWidth + px) * 4;
        // Background
        buffer[idx] = 30;
        buffer[idx + 1] = 30;
        buffer[idx + 2] = 50;
        buffer[idx + 3] = 255;

        // Animated center circle
        const dx = px - cx;
        const dy = py - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= radius) {
          const t = dist / radius;
          buffer[idx] = Math.floor(255 * (1 - t));
          buffer[idx + 1] = Math.floor(100 * (1 - t * 0.5));
          buffer[idx + 2] = Math.floor(100 * (1 - t));
          buffer[idx + 3] = 255;
        }
      }
    }

    win.render(win.pixelWidth, win.pixelHeight, win.pixelWidth * 4, 'bgra8888', buffer);

    frame++;
    await new Promise(resolve => setTimeout(resolve, 16)); // ~60 FPS
  }

  win.destroy();
  console.log('Window closed.');

} catch (err) {
  console.error('Error:', err.message);
  console.error(err.stack);
  process.exit(1);
}
