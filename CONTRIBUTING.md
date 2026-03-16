# Contributing to Argus

Thanks for your interest in contributing! Argus is an open-source project and we welcome contributions of all kinds.

## Quick Start

```bash
git clone https://github.com/itachi-hue/argus.git
cd argus
```

### Server (Python)

```bash
cd server
pip install -e ".[dev]"
ruff check src/ tests/
pytest
```

### Extension (TypeScript)

```bash
cd extension
npm install
npm run build
```

Load the `extension/dist` folder as an unpacked extension in Chrome (`chrome://extensions` → Developer mode → Load unpacked).

## Development Workflow

1. **Fork** the repo and create a feature branch from `main`.
2. **Make your changes** — keep commits focused and atomic.
3. **Test** your changes:
   - Server: `pytest` and `ruff check src/ tests/`
   - Extension: `npm run build` (ensure no TS errors)
4. **Open a PR** against `main` with a clear description.

## Project Structure

```
server/          → Python MCP server (FastAPI + MCP SDK)
  src/argus/
    api/         → HTTP & WebSocket routes, middleware
    core/        → Data stores, command queue
    mcp/         → MCP tool definitions
  tests/         → Pytest tests

extension/       → Chrome extension (Manifest V3)
  src/
    background/  → Service worker (WebSocket, event capture)
    content/     → Content scripts (DOM bridge)
    injected/    → Page-context scripts (console/error hooks)
    popup/       → Extension popup UI
```

## Code Style

- **Python**: We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting. Run `ruff check --fix src/ tests/` and `ruff format src/ tests/` before committing.
- **TypeScript**: Standard TypeScript with strict mode. The extension uses vanilla TS (no framework).

## What to Work On

- Check [open issues](https://github.com/itachi-hue/argus/issues) for bugs and feature requests.
- Issues labeled `good first issue` are great starting points.
- Have your own idea? Open an issue first to discuss it.

## Adding a New MCP Tool

1. Add the tool function in `server/src/argus/mcp/tools.py`.
2. If it needs browser interaction, add a command type in the extension's `executeCommand()` handler (`extension/src/background/index.ts`).
3. Add tests in `server/tests/`.
4. Update `README.md` with the new tool in the tools table.

## Reporting Bugs

Use the [Bug Report template](https://github.com/itachi-hue/argus/issues/new?template=bug_report.yml) — it helps us reproduce and fix issues faster.

## Code of Conduct

Be kind, respectful, and constructive. We're all here to build something useful together.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

