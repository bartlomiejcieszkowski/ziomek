# Gamify AI

Control VS Code and Copilot Chat with a gamepad. Modular architecture for extensible gamepad integration.

## Features

- Gamepad input mapped to VS Code commands and Copilot Chat actions
- Hot-reloadable settings (no restart needed)
- Context-aware: behaves differently based on what you're focused on
- Extensible module system for future gamepad-controlled features

## Settings

All settings under the `gamifyAI.*` namespace. Open VS Code Settings UI and search for "Gamify AI".

## Requirements

- A gamepad connected via USB or Bluetooth
- SDL2 (auto-installed by gamepad-node)

## Contributing

Future modules can be added by implementing the `GamepadModule` interface.
