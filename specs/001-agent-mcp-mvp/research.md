# Research: Agent MCP Server MVP

**Branch**: `001-agent-mcp-mvp` | **Date**: 2026-03-20

## Decisions

### Decision 1 — MCP Server Library

- **Decision**: Use `mcp` (PyPI) with the FastMCP high-level API (`mcp.server.fastmcp.FastMCP`)
- **Rationale**: FastMCP is the recommended, production-stable Python MCP SDK. It auto-generates JSON Schema from type annotations, supports async tools, and ships a test client (`fastmcp.Client`) that runs in-memory without a subprocess — directly satisfying the constitution's unit-test requirement. Current stable version: 1.7.1. Python ≥3.10 required.
- **Alternatives considered**: Low-level `Server` class (same package) — rejected: more boilerplate, no auto-schema generation, YAGNI (Principle II).

### Decision 2 — Agent Library

- **Decision**: Use `claude-agent-sdk` (PyPI, import `claude_agent_sdk`) with the `query()` async generator entry point
- **Rationale**: The canonical Python SDK for running Claude agents with MCP server support. `query()` handles subprocess lifecycle, MCP connection, tool permission checks, and message streaming with no manual wiring. Current version: 0.1.49. Python ≥3.10 required.
- **Alternatives considered**: Raw Anthropic API with manual MCP client — rejected: no built-in subprocess MCP support, requires re-implementing the tool-call loop. `ClaudeSDKClient` bidirectional client — deferred: needed only for interactive/multi-turn sessions, which are out of scope for MVP.

### Decision 3 — MCP Transport

- **Decision**: stdio only (agent launches MCP server as a subprocess via `python -m src.server`)
- **Rationale**: Explicitly specified in the spec (`Assumptions` section). The `claude-agent-sdk` `mcp_servers` config accepts `{command, args, env}` and manages the subprocess lifecycle. No HTTP/SSE configuration needed.
- **Alternatives considered**: HTTP/SSE transport — explicitly out of scope for MVP.

### Decision 4 — Python Version & Tooling

- **Decision**: Python 3.11, `pyproject.toml` (PEP 621), `uv` as package manager, `pytest` + `pytest-asyncio` for tests
- **Rationale**: Both `mcp` and `claude-agent-sdk` require Python ≥3.10; 3.11 is the current stable LTS with improved async error messages. `uv` is the modern fast resolver for Python projects. `pytest-asyncio` handles `async def` test functions without boilerplate.
- **Alternatives considered**: Python 3.12 — acceptable, but 3.11 has wider devcontainer support. `hatch` build backend — acceptable alternative to `uv`, but `uv` is faster.

### Decision 5 — Tool Result Shape

- **Decision**: FastMCP tools return a `dict` with named fields; agent accesses individual fields by key (FR-007)
- **Rationale**: FastMCP serializes dict returns as JSON in the MCP content payload. The constitution mandates every result include `file`, `start_line`, `end_line`, and `snippet` for search results — for MVP demo tools, a simpler named-field dict is appropriate (e.g., `{"result": ..., "status": "ok"}`). Structured output auto-generated from return type annotation.
- **Alternatives considered**: Plain text return — rejected: violates FR-007 (named content payload required) and constitution result schema requirements.

### Decision 6 — Error Surfacing

- **Decision**: Rely on FastMCP's built-in validation errors (returned as structured MCP error responses) and `claude-agent-sdk` error types (`CLIConnectionError`, `ProcessError`) for all failure modes
- **Rationale**: FastMCP automatically returns MCP error responses for schema validation failures. The SDK raises typed exceptions for connection failures. No custom error middleware needed (Principle II — YAGNI).
- **Alternatives considered**: Custom exception hierarchy — rejected: over-engineering for MVP; the existing SDK errors cover all required failure modes (FR-003, SC-003).

## Key Integration Patterns

### MCP Server bootstrap (stdio)
```python
# src/server/__main__.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("localsearch")  # server name used in tool routing

@mcp.tool()
def echo(message: str) -> dict:
    """Echo the input message back with a status field. Returns {result, status}."""
    return {"result": message, "status": "ok"}

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

### Agent connecting to MCP server
```python
# src/agent/main.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage, ResultMessage

async def run(prompt: str) -> str:
    options = ClaudeAgentOptions(
        mcp_servers={
            "localsearch": {
                "command": "python",
                "args": ["-m", "src.server"],
            }
        },
        allowed_tools=["mcp__localsearch__*"],
    )
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, SystemMessage) and msg.subtype == "init":
            failed = [s for s in msg.data.get("mcp_servers", []) if s.get("status") != "connected"]
            if failed:
                raise RuntimeError(f"MCP servers failed to connect: {failed}")
        if isinstance(msg, ResultMessage) and msg.subtype == "success":
            return msg.result
    raise RuntimeError("No result received")

if __name__ == "__main__":
    import sys
    print(asyncio.run(run(sys.argv[1])))
```

### Unit test (in-memory, no subprocess)
```python
# tests/unit/test_server_tools.py
import pytest
from fastmcp import Client
from src.server.__main__ import mcp

@pytest.mark.asyncio
async def test_echo_returns_named_fields():
    async with Client(mcp) as client:
        result = await client.call_tool("echo", {"message": "hello"})
    data = result[0].text  # JSON string
    import json
    parsed = json.loads(data)
    assert parsed["result"] == "hello"
    assert parsed["status"] == "ok"
```

## Gotchas & Notes

- **stdout hygiene**: Any `print()` in the MCP server corrupts the stdio protocol stream. Use `sys.stderr` or FastMCP's `Context` logging methods exclusively.
- **Tool naming**: SDK routes tools as `mcp__{server-name}__{tool-name}`. Server named `"localsearch"` + tool `echo` → `mcp__localsearch__echo`.
- **Connection timeout**: Default 60s. Servers that initialize slowly fail silently unless the `SystemMessage` init event is checked.
- **Tool search**: SDK auto-defers tool definitions when >10% of context is used by tool schemas. Requires Sonnet 4+ or Opus 4; Haiku does not support it.
- **Benchmark baseline**: Must be recorded before any change to the search/index pipeline (Principle V). For MVP, record round-trip latency of the `echo` tool as baseline.
