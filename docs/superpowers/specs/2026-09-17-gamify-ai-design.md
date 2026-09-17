# Gamify AI - Gamepad Control Extension Design

> **Goal:** Build a VS Code extension that maps gamepad input to VS Code and Copilot Chat commands, with a modular architecture extensible to future gamepad-controlled modules (Terminal, File Explorer, Git, etc.).

> **Architecture:** Three-layer design — a gamepad service captures raw input via gamepad-node, a mapping engine resolves abstract actions from configurable mappings, and a module registry routes actions to registered modules. Settings are hot-reloadable.

> **Tech Stack:** TypeScript, VS Code Extension API, gamepad-node (SDL2-based gamepad input), vscode-json-languageservice for config validation.

## Global Constraints

- Must work in VS Code desktop and GitHub Codespaces (extension host compatible)
- gamepad-node has native SDL2 bindings — works on desktop; web extensions fall back gracefully (no gamepad support in browser extension host)
- Zero other dependencies beyond gamepad-node and VS Code's built-in APIs
- Hot-reload settings changes without extension restart
- Default gamepad mapping shipped with the extension
- All gamepad input must be debounced/deduplicated to avoid duplicate actions
- Extension must handle gamepad connect/disconnect without crashing
- Settings schema must be JSON Schema compliant with friendly descriptions for the VS Code settings UI

---

## 1. Gamepad Service

### Responsibility

Low-level gamepad input capture. Polls connected gamepads at a configurable interval via `gamepad-node`, normalizes input into typed events, and manages the lifecycle of gamepad connections.

### Design

- Uses `gamepad-node` (which mirrors the browser Gamepad API but on the Node side with SDL2 bindings)
- `GamepadService` class with:
  - `poll()` — called on an interval timer, reads all connected gamepads
  - Events: `gamepad:connect`, `gamepad:disconnect`, `gamepad:button`, `gamepad:axis`
  - Each event carries a `GamepadId` (index) and a `GamepadState` (snapshot of buttons/axes)
- Interval configurable via `gamifyAI.pollingIntervalMs` (default: 16ms / ~60Hz)
- If no gamepad is connected, the polling loop still runs but emits no events
- On disconnect, the service emits a `gamepad:disconnect` event so the mapping engine can clean up state

### Why gamepad-node over the browser Gamepad API?

The browser Gamepad API is only available in the browser-based extension host. `gamepad-node` wraps SDL2 and exposes the same W3C Gamepad API on the Node side, so our service code is uniform regardless of host. In the web extension host (GitHub Codespaces), we detect the environment and gracefully disable gamepad functionality with a user notification.

### Key types

```typescript
interface GamepadState {
  id: string;
  index: number;
  connected: boolean;
  buttons: ReadonlyArray<{ pressed: boolean; value: number }>;
  axes: ReadonlyArray<number>;
}
```

---

## 2. Mapping Engine

### Responsibility

Translates raw gamepad events into typed abstract actions using a configurable mapping table. Acts as the bridge between hardware and extension features.

### Design

- `MappingEngine` listens to gamepad service events
- Reads mapping config from VS Code settings under `gamifyAI.modules.<moduleName>.mapping`
- Resolves a `GamepadAction` from a button press:
  - Example: `GamepadState` event on button 0 (A) in module `copilotChat` → resolves to action `send-message`
- Uses a state machine to handle button transitions:
  - `pressed` → fire action only once (on press edge, not held)
  - `released` → optionally fire a separate action (e.g., "cancel" on button release)
- Supports axis-to-action resolution:
  - Analog stick deflection on a threshold (configurable, default: 0.5) maps to actions like "scroll-up", "scroll-down"
  - Dead zone prevents jitter from worn sticks (default: 0.3)
- Configurable debounce: `gamifyAI.debounceMs` (default: 80ms) prevents rapid duplicate firing
- Settings changes are watched; when the mapping changes, the engine reloads immediately

### Key types

```typescript
type ButtonAction = 'send-message' | 'new-chat' | 'cancel' | 'open-slash-menu' | 'close-panel' | string;
type DpadAction = 'focus-up' | 'focus-down' | 'focus-left' | 'focus-right' | string;
type AxisAction = 'scroll-up' | 'scroll-down' | 'scroll-left' | 'scroll-right' | string;
type TriggersAction = 'step-forward' | 'step-backward' | string;

interface ModuleMapping {
  buttons: Record<number, ButtonAction>;
  dpad: Record<0 | 1 | 2 | 3, DpadAction>; // 0=up, 1=right, 2=down, 3=left
  axes: { xAxis?: [number, AxisAction]; yAxis?: [number, AxisAction] };
  triggers?: { left?: TriggersAction; right?: TriggersAction };
}
```

### Default Mapping (copilotChat module)

| Button/Axis | Default Action |
|-------------|----------------|
| A (button 0) | `send-message` |
| B (button 1) | `cancel` |
| X (button 2) | `new-chat` |
| Y (button 3) | `open-slash-menu` |
| D-Pad Up | `focus-up` |
| D-Pad Down | `focus-down` |
| D-Pad Left | `focus-left` |
| D-Pad Right | `focus-right` |
| Left Stick Y | `scroll-up` / `scroll-down` (threshold-based) |
| L1 (button 4) | `scroll-up` (page up) |
| R1 (button 5) | `scroll-down` (page down) |
| L2 (button 6) | `step-forward` |
| R2 (button 7) | `step-backward` |
| Start (button 9) | `toggle-panel` |
| Select (button 8) | `open-command-palette` |

---

## 3. Module Registry

### Responsibility

Pluggable system for gamepad-controlled features. Each module declares what actions it handles, what context it cares about, and how to execute actions.

### Design

- `ModuleRegistry` — single registry that modules register with
- Each module implements the `GamepadModule` interface:
  - `name`: identifier (e.g., `'copilotChat'`)
  - `displayName`: human-readable name
  - `actions`: list of action names this module responds to
  - `contexts`: list of contexts this module is relevant in
  - `execute(action, context, moduleId)`: resolves and executes an action
- The registry provides a `resolve(moduleId, action, context)` → `Promise<void>`
- If no module claims the action in the given context, the event is silently dropped (or can forward to VS Code's default keybindings)
- Modules can register a `priority` — if multiple modules claim the same action, the highest priority wins

### Base Interface

```typescript
interface GamepadModule {
  name: string;
  displayName: string;
  actions: readonly string[];
  contexts: readonly string[];
  execute(action: string, context: ContextState): Promise<void>;
}
```

---

## 4. Copilot Chat Module

### Responsibility

First concrete module — maps gamepad actions to Copilot Chat operations.

### Actions

| Action | Implementation |
|--------|----------------|
| `send-message` | Calls `vscode.commands.executeCommand('chat.sendRequest')` with input from current chat input |
| `new-chat` | Calls `vscode.commands.executeCommand('workbench.action.chat.newChat')` |
| `cancel` | Calls `vscode.commands.executeCommand('cancelNotification')` or `chat.cancel` |
| `open-slash-menu` | Focuses the chat input and calls `vscode.commands.executeCommand('chat.triggerSlash')` |
| `toggle-panel` | Calls `vscode.commands.executeCommand('workbench.action.chat.toggle')` |
| `open-command-palette` | Calls `vscode.commands.executeCommand('workbench.action.showCommands')` |
| `focus-up` / `focus-down` / `focus-left` / `focus-right` | Calls `workbench.action.navigate*` or moves focus between panels |
| `scroll-up` / `scroll-down` | Scrolls the chat view up/down using keyboard equivalents (`ArrowUp` / `ArrowDown` or `PageUp` / `PageDown`) |
| `step-forward` / `step-backward` | Navigates between code blocks in chat responses using `workbench.action.nextEditor` / `workbench.action.previousEditor` (or scrolls to next/previous code block) |

### Context Awareness

The module respects the current UI context:
- If input field is focused → send-message sends text, slash menu opens `/`
- If a message is selected → cancel stops streaming, copy copies the message
- If sidebar is focused → navigation moves between sidebar items

### Context Tracking

A generic `ContextTracker` observes VS Code focus changes:
- Listens to `onDidChangeTextEditorSelection`, `onDidChangeActiveTextEditor`, `onDidChangeActivePanelView`, and related events
- Exposes a `ContextState` with fields: `activePanel`, `inputFocused`, `chatFocused`, `streaming`, etc.
- Modules can subscribe to context changes

---

## 5. Settings & Configuration

### Responsibility

Provide a user-friendly settings experience with full customization of gamepad behavior.

### Design

- All settings under `gamifyAI.*` namespace
- `gamifyAI.enabled` (default: true) — master toggle for the extension
- `gamifyAI.pollingIntervalMs` (default: 16) — how often to poll gamepad state
- `gamifyAI.debounceMs` (default: 80) — minimum time between repeated actions
- `gamifyAI.modules` — per-module configuration:
  - `<moduleName>.enabled` (default: true) — whether the module is active
  - `<moduleName>.mapping` — full mapping table (buttons, dpad, axes, triggers)
- Settings use JSON Schema with descriptions for the VS Code settings UI
- Settings changes are watched via `vscode.workspace.onDidChangeConfiguration` and hot-reloaded
- Default mapping values are shipped in the extension and appear if the user has not overridden them

### Settings JSON Schema

Schema defines:
- All settings with types, defaults, and descriptions
- Nested structure for module mappings
- Enum values where applicable (e.g., valid action names)
- Validation errors surface in the VS Code settings editor

---

## 6. Extension Lifecycle

### Responsibility

Wire everything together and manage the extension's lifetime.

### Design

- `activate(context)` in `src/extension.ts`:
  1. Read config
  2. Create `GamepadService` with polling interval
  3. Create `ContextTracker` (listens to VS Code focus events)
  4. Create `ModuleRegistry` and register all known modules (Copilot Chat first)
  5. Create `MappingEngine`, wire it to the gamepad service events
  6. Connect mapping engine output to the module registry
  7. Register a `onDidChangeConfiguration` listener for hot-reload
  8. Register any debug/command helpers (e.g., a "Test Gamepad" command for diagnostics)
- `deactivate()`:
  1. Cancel the polling interval
  2. Clean up all listeners
  3. Dispose of gamepad-node resources

### Diagnostics Command

- Register a command `gamifyAI.showDebugInfo` that outputs the current gamepad state, active mappings, and module registry to the VS Code output channel
- Useful for troubleshooting

---

## File Structure

```
package.json
README.md
src/
  extension.ts            # Activation, lifecycle, wiring
  gamepad/
    service.ts            # gamepad-node bridge, polling loop
    events.ts             # Typed event definitions, types
    index.ts              # Barrel export
  mapping/
    config.ts             # Config schema, validation, hot-reload watcher
    resolver.ts           # Button/axis → action resolution, state machine
    index.ts              # Barrel export
  modules/
    base.ts               # GamepadModule interface, ModuleRegistry
    copilot-chat.ts       # Copilot Chat module implementation
    index.ts              # Barrel export
  context.ts              # ContextTracker — focus/state awareness
types/
  gamepad.d.ts            # gamepad-node type shims (if needed)
```

---

## Scope

This spec covers the foundational architecture and the first module (Copilot Chat). Future work (separate specs) includes:

- Terminal module — gamepad navigation and command input in the integrated terminal
- File Explorer module — browse files, open files, navigate folders
- Git module — browse staged/unstaged files, stage, commit, push
- Custom module system — allow users to define their own module mappings or ship community modules

---

## Self-Review

1. **Placeholder scan:** No TBDs or TODOs. All types and interfaces are concrete.
2. **Internal consistency:** Gamepad service feeds mapping engine feeds module registry — consistent data flow. Settings schema supports all described config. Context tracker feeds into all modules — consistent.
3. **Scope check:** Focused on foundation + one module. Future modules are acknowledged but excluded — scope is tight.
4. **Ambiguity check:** Hot-reload mechanism is explicit (onDidChangeConfiguration listener). Button edge detection is specified (fire on press, not held). Debounce is specified with default value. Web extension host fallback is specified.

---

*Spec written: 2026-09-17*
