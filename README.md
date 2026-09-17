# Gamify AI

Control VS Code and Copilot Chat with a gamepad. Modular architecture for extensible gamepad integration.

## Features

- **Copilot Chat Control**: Send messages, start new chats, navigate responses
- **VS Code Navigation**: Focus up/down/left/right, scroll through content
- **Context Aware**: Behaves differently based on what you're focused on
- **Fully Configurable**: Remap any button, axis, or trigger via VS Code settings

## Default Gamepad Mapping

| Input | Action |
|-------|--------|
| A (South) | Send message |
| B (East) | Cancel / Stop streaming |
| X (West) | New chat |
| Y (North) | Open slash menu |
| D-Pad Up | Focus up |
| D-Pad Down | Focus down |
| D-Pad Left | Focus left |
| D-Pad Right | Focus right |
| L1 | Scroll up |
| R1 | Scroll down |
| L2 | Step forward (next code block) |
| R2 | Step backward (previous code block) |
| Start | Toggle Copilot Chat panel |
| Select | Open command palette |
| Left Stick | Scroll chat content |

## Installation

1. Build: `npm run compile`
2. Press F5 in VS Code to launch extension host
3. Connect your gamepad

## Development

```bash
npm install
npm run watch      # Auto-recompile on changes
npm test           # Run tests
```

## Contributing

The module system is extensible. Create a new module by implementing the `GamepadModule` interface in `src/modules/` and registering it in `src/extension.ts`.
