import { installNavigatorShim } from 'gamepad-node';

console.log('=== Gamepad Diagnostic ===\n');

let manager = null;
let connectedGamepads = [];

try {
  console.log('[1] Installing gamepad-node shim...');
  manager = installNavigatorShim();
  console.log('  ✅ gamepad-node installed successfully');
  console.log('  manager:', {
    hasOn: typeof manager.on === 'function',
    hasStartPolling: typeof manager.startPolling === 'function',
    hasPoll: typeof manager.poll === 'function',
    hasGetGamepads: typeof manager.getGamepads === 'function',
  });

  manager.on('gamepadconnected', (event) => {
    console.log('\n✅ GAMEPAD CONNECTED:', event.gamepad.id);
    console.log('  index:', event.gamepad.index);
    console.log('  buttons:', event.gamepad.buttons.length);
    console.log('  axes:', event.gamepad.axes.length);
    console.log('  mapping:', event.gamepad.mapping);
    connectedGamepads.push(event.gamepad);
  });

  manager.on('gamepaddisconnected', (event) => {
    console.log('\n❌ GAMEPAD DISCONNECTED:', event.gamepad.id);
  });

  console.log('\n[2] Starting poll (5s)...');
  manager.startPolling(60);

  // Poll every 500ms to check state
  setInterval(() => {
    try {
      const gamepads = navigator.getGamepads();
      let foundNew = false;
        for (let i = 0; i < gamepads.length; i++) {
        if (gamepads[i]) {
          const gp = gamepads[i];
          const already = connectedGamepads.find(g => g.index === i);
          if (!already) {
            connectedGamepads.push(gp);
            console.log(`\n✅ Found gamepad ${i}: ${gp.id.substring(0, 50)}`);
          }
          const pressed = gp.buttons.filter(b => b.pressed);
          if (pressed.length > 0) {
            console.log(`\n🎮 Button pressed on gamepad ${i}: ${pressed.map(b => `btn[${b.index}]=${b.value.toFixed(2)}`).join(', ')}`);
          }
          const nonZeroAxes = gp.axes.map((a, idx) => ({ idx, value: a })).filter(a => Math.abs(a.value) > 0.1);
          if (nonZeroAxes.length > 0) {
            console.log(`\n🎮 Axes active on gamepad ${i}: ${nonZeroAxes.map(a => `axis[${a.idx}]=${a.value.toFixed(2)}`).join(', ')}`);
          }
        }
      }
    } catch (e) {
      console.log('Poll error:', e.message);
    }
  }, 500);

  // Stop after 5 seconds and print summary
  setTimeout(() => {
    console.log('\n[3] Final count:', connectedGamepads.length, 'gamepad(s) detected');
    if (connectedGamepads.length > 0) {
      console.log('\n🎮 All detected gamepads:');
      for (const gp of connectedGamepads) {
        console.log(`  - ${gp.id.substring(0, 50)} (index ${gp.index})`);
      }
    } else {
      console.log('\n⚠️ No gamepads detected after 5 seconds.');
      console.log('Troubleshooting:');
      console.log('  1. Run "control joysticks" from Win+R to check Windows sees your controller');
      console.log('  2. Close Steam, Xbox app, or any other gamepad software');
      console.log('  3. Try a different USB port');
      console.log('  4. Some controllers (PS4/PS5) need DS4Windows');
    }
    manager.startPolling(0); // Stop polling
    console.log('\n=== Done ===');
  }, 5000);

} catch (error) {
  console.log('❌ gamepad-node failed to initialize:');
  console.log('  Error:', error.message);
  console.log('  Code:', error.code);
  console.log('\nThis usually means SDL2 is not installed or can\'t find controllers.');
}
