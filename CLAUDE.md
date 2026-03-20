# workspace Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-20

## Active Technologies
- Python 3.11 + `mcp` (FastMCP, stdio server), `watchdog>=4.0` (file system events), `anyio` (transitive via mcp — MemoryObjectStream bridge, fail_after debounce), `claude-agent-sdk` (agent orchestration) (002-mcp-file-monitoring)
- In-process only — `dict` registry + `deque` event buffer; no persistence (002-mcp-file-monitoring)

- Python 3.11 + `mcp` (FastMCP, stdio server), `claude-agent-sdk` (agent orchestration), `pytest`, `pytest-asyncio` (001-agent-mcp-mvp)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.11: Follow standard conventions

## Recent Changes
- 002-mcp-file-monitoring: Added Python 3.11 + `mcp` (FastMCP, stdio server), `watchdog>=4.0` (file system events), `anyio` (transitive via mcp — MemoryObjectStream bridge, fail_after debounce), `claude-agent-sdk` (agent orchestration)

- 001-agent-mcp-mvp: Added Python 3.11 + `mcp` (FastMCP, stdio server), `claude-agent-sdk` (agent orchestration), `pytest`, `pytest-asyncio`

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
