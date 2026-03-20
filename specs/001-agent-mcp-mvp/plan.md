# Implementation Plan: Agent MCP Server MVP

**Branch**: `001-agent-mcp-mvp` | **Date**: 2026-03-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-agent-mcp-mvp/spec.md`

## Summary

Build a minimal Python project demonstrating a Claude agent (via `claude-agent-sdk`) calling a tool exposed by a local MCP server (via `mcp`/FastMCP) over stdio transport. The agent launches the MCP server as a subprocess, calls a tool with structured input, and receives a named key-value result. Error paths (unavailable server, missing tool, bad input) are surfaced as structured MCP error responses.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `mcp` (FastMCP, stdio server), `claude-agent-sdk` (agent orchestration), `pytest`, `pytest-asyncio`
**Storage**: N/A
**Testing**: pytest + pytest-asyncio; FastMCP in-memory `Client(server)` for unit tests; subprocess integration tests for end-to-end
**Target Platform**: Linux (local dev environment, same machine)
**Project Type**: CLI / library integration demo
**Performance Goals**: Tool call result returned within 5 seconds (SC-002)
**Constraints**: stdio transport only; no HTTP/SSE; no auth; single agent, single server; sequential tool calls only
**Scale/Scope**: MVP — one MCP server, one or more demo tools, one agent entrypoint

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Token Efficiency** | ✅ PASS | Tool results are structured key-value payloads (FR-007); no full-file dumps. MCP tool description must be ≤3 sentences, informative, no marketing language (Principle IV). |
| **II. Simplicity Over Cleverness** | ✅ PASS | FastMCP high-level API; `query()` top-level function; no custom abstraction layers. Single server, single agent. |
| **III. Concurrent & Non-Blocking I/O** | ✅ PASS | FastMCP supports async tools; `claude-agent-sdk` uses async/await throughout. MCP server stdio transport is non-blocking by design. |
| **IV. Precise Trigger Surface** | ✅ PASS | Tool descriptions must be ≤3 sentences, self-documenting parameter names. Will be enforced in server implementation. |
| **V. Performance-Aware Design** | ✅ PASS | SC-002 requires <5s response time. FastMCP in-process test client avoids subprocess overhead for unit tests. Benchmark baseline to be recorded. |

**Gate result**: PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-mcp-mvp/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── server/
│   ├── __init__.py
│   └── __main__.py       # FastMCP server: mcp.run(transport="stdio")
└── agent/
    ├── __init__.py
    └── main.py           # claude_agent_sdk query() entry point

tests/
├── unit/
│   └── test_server_tools.py   # FastMCP in-memory Client(server) tests
├── integration/
│   └── test_agent_mcp.py      # subprocess end-to-end tests
└── contract/
    └── test_tool_schema.py    # tool input/output schema validation

pyproject.toml
.mcp.json                      # static MCP server config (auto-loaded by SDK)
```

**Structure Decision**: Single project layout (Option 1). No frontend, no mobile, no separate backend service. Server and agent coexist under `src/` as two top-level packages; tests mirror the three test types mandated by the constitution (unit, integration, contract).

## Complexity Tracking

> No constitution violations — table not required.

---

## Phase 0: Research

> Research complete — findings consolidated below and in [research.md](research.md).

---

## Phase 1: Design & Contracts

> Artifacts: [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

### Logical Groups (per user input)

The feature breaks down into four cohesive logical groups:

#### Group 1 — MCP Server & Tool Definition
Everything needed to stand up a FastMCP server that exposes at least one well-described, schema-validated tool over stdio.

- FastMCP server bootstrap (`__main__.py`, `mcp.run(transport="stdio")`)
- Tool definition with typed input params and structured dict return
- Tool description ≤3 sentences (Principle IV)
- stderr-only logging (stdout is the protocol stream)
- `pyproject.toml` entry point so the server is runnable as `python -m src.server`

#### Group 2 — Agent & MCP Connection
Everything needed for the Claude agent to launch the MCP server as a subprocess and call its tools.

- `ClaudeAgentOptions` with `mcp_servers` pointing to `python -m src.server`
- `allowed_tools` scoped to `mcp__<server-name>__*`
- `query()` loop with `SystemMessage` init check for connection status
- `ResultMessage` extraction for final output
- Timeout handling (default 60s MCP connection timeout)

#### Group 3 — Error Handling
Everything needed to surface structured errors for all failure modes (FR-003, SC-003).

- Unavailable server → `CLIConnectionError` / timeout surfaced to caller
- Non-existent tool → MCP error response forwarded by agent
- Malformed input → schema validation error from FastMCP returned as structured MCP error
- Empty/null result → agent handles and reports (not a silent pass)
- No indefinite hangs (agent-level timeout enforced)

#### Group 4 — Testing & Developer Experience
Everything needed to verify the integration and meet SC-004 (≤10 min setup).

- Unit tests: FastMCP `Client(server)` in-memory (no subprocess) for each tool
- Contract tests: tool input/output schema validates against JSON Schema spec
- Integration test: subprocess end-to-end — agent calls tool, result verified
- `quickstart.md`: documented setup steps, expected output
- `.mcp.json` static config so SDK auto-loads the server
- Benchmark baseline recorded for tool call round-trip (Principle V)
