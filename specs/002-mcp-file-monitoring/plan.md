# Implementation Plan: MCP File Monitoring

**Branch**: `002-mcp-file-monitoring` | **Date**: 2026-03-20 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-mcp-file-monitoring/spec.md`

## Summary

Add file and directory monitoring to the existing FastMCP server (`src/server`). The agent registers paths via a `register_files` MCP tool; the server uses `watchdog` (Observer thread) bridged into asyncio via `anyio.MemoryObjectSendStream.send_nowait`, debounces rapid events in a single async task, and exposes accumulated `ChangeEvent` records through a `poll_events` tool. The agent polls on a schedule. Three additional tools — `deregister_files`, `list_monitored`, and `poll_events` — complete the four-tool surface. All tests are end-to-end against a real MCP subprocess with real file I/O; no mocks.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: `mcp` (FastMCP, stdio server), `watchdog>=4.0` (file system events), `anyio` (transitive via mcp — MemoryObjectStream bridge, fail_after debounce), `claude-agent-sdk` (agent orchestration)
**Storage**: In-process only — `dict` registry + `deque` event buffer; no persistence
**Testing**: `pytest`, `pytest-asyncio` — all tests end-to-end (real MCP subprocess + real file I/O); no mocks
**Target Platform**: Linux (dev), cross-platform via watchdog
**Project Type**: MCP server + agent orchestration library
**Performance Goals**: Registration confirmation ≤1s (SC-001); change notification delivery ≤2s (SC-002); 500 monitored files without degradation (SC-003)
**Constraints**: No blocking I/O on event loop; watchdog Observer thread bridges via `send_nowait` only (never writes to registry); debounce window coalesces burst of N events into 1 per file per window (SC-004)
**Scale/Scope**: Single agent session; global shared registry; up to ~500 paths; ephemeral (no restart persistence)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Token Efficiency | ✅ PASS | Tool responses include only path, event_type, timestamp, count — no full-file dumps |
| II. Simplicity Over Cleverness | ✅ PASS | Global `dict` registry, single `deque` buffer, one debounce task — no abstraction layers beyond what's needed for two call sites (register + debounce) |
| III. Concurrent and Non-Blocking I/O | ✅ PASS | watchdog Observer runs in its own thread; async tool handlers don't block; debounce task uses `anyio.fail_after` not `asyncio.sleep` polling |
| IV. Precise Trigger Surface | ✅ PASS | Tool descriptions are ≤3 sentences, parameter names self-documenting (see contracts/mcp-tools.md) |
| V. Performance-Aware Design | ✅ PASS | No per-file tasks; single debounce task; bounded deque prevents unbounded memory growth |
| VI. End-to-End Testing Discipline | ✅ PASS | All tests use real MCP subprocess + real file I/O; `test_debounce.py` uses real asyncio (no mocks) |

**Post-Phase 1 re-check**: All principles still satisfied. The polling delivery model (Decision 1 in research.md) is the simplest correct approach given SDK constraints; no additional complexity was introduced.

## Project Structure

### Documentation (this feature)

```text
specs/002-mcp-file-monitoring/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── mcp-tools.md     # Phase 1 output — 4 tool schemas
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code

```text
src/
└── server/
    ├── __init__.py       # (exists, empty)
    ├── __main__.py       # FastMCP app entry point — add lifespan, register 4 new tools
    ├── monitor.py        # NEW: MonitoredEntry, registry dict, watchdog handler, ChangeEvent buffer
    └── debounce.py       # NEW: async debounce task (MemoryObjectStream → deque)

tests/
├── contract/
│   └── test_tool_schema.py    # extend: add schema tests for 4 new tools
├── integration/
│   ├── test_agent_mcp.py      # (exists: echo tool tests)
│   ├── test_register.py       # NEW: US1 — register/deregister/list via real MCP subprocess
│   ├── test_notifications.py  # NEW: US2 — file change → poll_events (real file I/O)
│   └── test_deregister.py     # NEW: US3 — deregister stops notifications
└── unit/
    └── test_debounce.py       # NEW: debounce logic (real asyncio, anyio MemoryObjectStream, no mocks)
```

**Structure Decision**: Single-project layout (Option 1). Extends existing `src/server` package with two new modules (`monitor.py`, `debounce.py`). New test files parallel user stories. The existing echo tool and its tests are preserved unchanged.

## Complexity Tracking

> No Constitution violations requiring justification. All abstractions (`monitor.py`, `debounce.py`) eliminate real duplication across at least two call sites (`register_files`/`deregister_files` share registry; debounce task reused across all watched paths).
