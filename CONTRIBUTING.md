# Contributing to Argus

Thanks for your interest in contributing! Here's how to get set up and submit changes.

## Development Setup

### Server (Python)

```bash
cd server
pip install -e ".[dev]"
```

### Extension (TypeScript)

```bash
cd extension
npm install
npm run build
```

Load the extension in Chrome: `chrome://extensions` → Developer mode → Load unpacked → select the `extension/` folder.

## Running Tests

```bash
# Server — 140+ tests
cd server
pytest tests/ -v

# Extension — 76 tests
cd extension
npm test
```

## Code Quality

```bash
# Python lint + format
cd server
ruff check src/ tests/
ruff format src/ tests/

# TypeScript type check
cd extension
npx tsc --noEmit
```

All checks run automatically in CI on push and pull requests.

## Submitting Changes

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Add or update tests for your changes
4. Ensure all tests pass and linting is clean
5. Open a pull request with a clear description

## Project Structure

- `server/src/argus/` — Python MCP server (FastAPI + MCP tools)
- `server/tests/` — Python tests (pytest)
- `extension/src/` — Chrome extension (TypeScript, Manifest V3)
- `extension/tests/` — Extension tests (vitest + jsdom)
- `docs/` — Architecture documentation

## Style Guide

- **Python**: Follows [ruff](https://docs.astral.sh/ruff/) defaults with the config in `pyproject.toml`
- **TypeScript**: `strict` mode, 2-space indent, see `tsconfig.json` and `.editorconfig`
- Write docstrings for public functions
- Use type annotations

