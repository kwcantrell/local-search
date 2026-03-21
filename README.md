# agent-mcp-mvp

A proof-of-concept demonstrating an AI agent (Claude) orchestrating tools through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) via stdio transport, with real-time file system monitoring.

## Overview

This project implements a full agent-MCP integration loop:

1. A **FastMCP server** (`src/server`) exposes tools over stdio
2. A **Claude agent** (`src/agent`) uses `claude-agent-sdk` to process prompts and invoke those tools
3. End-to-end integration tests validate the full roundtrip with real subprocess execution and real file I/O

### Available Tools

| Tool | Description |
|------|-------------|
| `echo` | Echo a message back with a status field |
| `register_files` | Register file/directory paths for change monitoring |
| `list_monitored` | List all currently monitored paths with metadata |
| `poll_events` | Retrieve debounced file change events since a given timestamp |
| `deregister_files` | Remove paths from monitoring |

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- [Claude Code CLI](https://claude.ai/code) installed and available in `PATH`

## Installation

```bash
uv sync           # Runtime dependencies
uv sync --dev     # Include dev dependencies (pytest, pytest-asyncio, ruff)
```

## Usage

**Run the MCP server standalone (stdio transport):**

```bash
uv run python -m src.server
```

**Run the agent with a prompt:**

```bash
uv run python -m src.agent "Use the echo tool with the message 'hello'"
uv run python -m src.agent "Register /tmp/myfile.txt for monitoring and poll for changes every 5 seconds"
```

**Typical file monitoring interaction:**

```
Agent → register_files(paths=["/tmp/foo.txt"])
Server → {"registered": ["/tmp/foo.txt"], "already_monitored": [], "errors": []}

# ... file changes ...

Agent → poll_events(since_ts=0.0)
Server → {"events": [{"path": "/tmp/foo.txt", "event_type": "modified", "timestamp": 1711234567.89}], "count": 1}

Agent → deregister_files(paths=["/tmp/foo.txt"])
Server → {"deregistered": ["/tmp/foo.txt"], "not_monitored": []}
```

## Configuration

File monitoring behaviour can be tuned via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBOUNCE_WINDOW_SECS` | `0.5` | Seconds to wait after first event before flushing a coalesced notification |
| `EVENT_BUFFER_MAXLEN` | `1000` | Maximum number of change events held in the in-memory buffer |
| `EVENT_QUEUE_MAXSIZE` | `256` | Maximum raw events in the watchdog→asyncio bridge queue (drops on overflow) |

## Development

**Run tests:**

```bash
uv run pytest                    # All tests (53 total)
uv run pytest tests/unit/        # Unit-level tests (debounce logic, MCP client)
uv run pytest tests/integration/ # End-to-end agent → server roundtrip + file I/O
uv run pytest tests/contract/    # Tool schema contract validation
```

**Lint:**

```bash
uv run ruff check .
```

## Project Structure

```
src/
  server/
    __main__.py   # FastMCP app entry point — lifespan, 5 tool definitions
    monitor.py    # MonitoredEntry registry, watchdog handler, ChangeEvent buffer
    debounce.py   # Async debounce task (MemoryObjectStream → deque)
  agent/          # Claude agent orchestration via claude-agent-sdk
tests/
  unit/           # Debounce logic + direct MCP client session tests
  integration/    # Full agent-MCP subprocess roundtrip + file monitoring tests
  contract/       # JSON schema contract tests for all tool outputs
```

## Architecture

The agent and server communicate over stdio using the MCP protocol. The agent spawns the server as a subprocess, discovers available tools, and Claude decides when and how to invoke them based on the user's prompt.

```
User Prompt → Agent (claude-agent-sdk) → MCP Client → subprocess → FastMCP Server → Tool
```

File monitoring uses [watchdog](https://github.com/gorakhargosh/watchdog) with an async debounce pipeline:

```
File System → watchdog Observer (thread) → MemoryObjectSendStream → debounce task → event buffer → poll_events
```

### Notes

- The `query()` async generator from `claude-agent-sdk` uses an anyio `TaskGroup` internally. To avoid cross-task cancel scope errors, the agent consumes the generator to completion rather than breaking out early, and uses `asyncio.timeout()` (Python 3.11+) instead of `asyncio.wait_for()` for timeouts.
- The watchdog Observer runs in its own thread and bridges into the async event loop via `send_nowait` only — it never directly touches the registry.
- All tests are end-to-end against a real MCP subprocess with real file I/O; no mocks.
