# Pi Developer Rules

## Commit discipline
- **Always commit changes after doing a task** — never leave work uncommitted.

## Approval discipline
- **Without explicit user acknowledgment** — do not act. Wait for confirmation before executing destructive or significant changes.

## Process discipline
- **Never loop** — if a command has already been applied, do not re-run it. Check status before acting.
- **NEVER kill python.exe** — the LLM process is running inside it. Only target project-specific processes (ziomek.exe, etc.).
- **Line endings** — respect `.gitattributes`. Do not "fix" line endings that are already correct (CRLF for Windows .bat/.cmd/.ps1, LF for .sh).

## Code organization
- **Use `uv run`** — do not install packages globally or into `.venv` at root. All Python projects manage their own venvs and dependencies.
- **Project structure** — keep the repo root clean. Each project type (python/, vscode_extension/, etc.) is self-contained.
