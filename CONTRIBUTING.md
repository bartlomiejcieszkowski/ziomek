# Contributing to Ziomek

## Quick Setup

```bash
uv sync                           # install dependencies and .venv
uv run python -m ziomek.cli serve # run the TTS server
uv run pytest tests/              # run tests
uv run ruff check .               # linting
```

## Project Structure

```text
.
├── src/ziomek/        # Python package (src layout)
├── tests/             # Test suite
├── vscode_extension/  # VS Code extension
├── docs/              # Documentation (internal/)
└── debug_tools/       # Development utilities
```

## Python Code Style

- Line length: 120 (configured in `pyproject.toml`)
- Linting: `ruff` (auto-import sorting via `select = ["I"]`)
- Type hints: encouraged throughout

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance
- `refactor:` — code restructuring
- `ci:` — CI workflow changes

Always sign-off: `-s` flag on `git commit`.

## Pull Requests

- Rebase on `main` before submitting
- Include tests for new features
- Keep PRs focused — one thing per PR
