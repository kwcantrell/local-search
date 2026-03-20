# agent-mcp-mvp

A minimal proof-of-concept demonstrating an AI agent (Claude) orchestrating tools through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) via stdio transport.

## Overview

This MVP implements a full agent-MCP integration loop:

1. A **FastMCP server** (`src/server`) exposes tools over stdio
2. A **Claude agent** (`src/agent`) uses `claude-agent-sdk` to process prompts and invoke those tools
3. End-to-end integration tests validate the full roundtrip with real subprocess execution

The current implementation uses a simple `echo` tool as the proof-of-concept.

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
```

## Development

**Run tests:**

```bash
uv run pytest                    # All tests
uv run pytest tests/unit/        # Unit-level MCP client tests
uv run pytest tests/integration/ # End-to-end agent → server roundtrip
uv run pytest tests/contract/    # Tool schema contract validation
```

**Lint:**

```bash
uv run ruff check .
```

## Project Structure

```
src/
  server/      # FastMCP server with tool definitions
  agent/       # Claude agent orchestration via claude-agent-sdk
tests/
  unit/        # Direct MCP client session tests
  integration/ # Full agent-MCP subprocess roundtrip tests
  contract/    # JSON schema contract tests for tool outputs
```

## Architecture

The agent and server communicate over stdio using the MCP protocol. The agent spawns the server as a subprocess, discovers available tools, and Claude decides when and how to invoke them based on the user's prompt.

```
User Prompt → Agent (claude-agent-sdk) → MCP Client → subprocess → FastMCP Server → Tool
```

### Notes

- The `query()` async generator from `claude-agent-sdk` uses an anyio `TaskGroup` internally. To avoid cross-task cancel scope errors, the agent consumes the generator to completion rather than breaking out early, and uses `asyncio.timeout()` (Python 3.11+) instead of `asyncio.wait_for()` for timeouts.
