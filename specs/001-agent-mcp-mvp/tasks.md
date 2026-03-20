# Tasks: Agent MCP Server MVP

**Input**: Design documents from `/specs/001-agent-mcp-mvp/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — directory layout, dependency manifest, tooling config

- [x] T001 Create project directory structure: `src/server/`, `src/agent/`, `tests/unit/`, `tests/integration/`, `tests/contract/`
- [x] T002 Create `pyproject.toml` with Python 3.11, `mcp`, `claude-agent-sdk`, `pytest`, `pytest-asyncio` dependencies, `[project.scripts]` entry point for `src.server`, and `[tool.ruff]` linting config (constitution §Development Workflow requires linter config in Phase 1 Setup)
- [x] T003 [P] Create `src/server/__init__.py` and `src/agent/__init__.py` (empty package markers)
- [x] T004 [P] Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/contract/__init__.py` (empty package markers)

**Checkpoint**: Project structure and linting config in place — run `ruff check src/ tests/` (should pass on empty files) before proceeding

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create `src/server/__main__.py` — bootstrap `FastMCP("localsearch")` instance and call `mcp.run(transport="stdio")` in `__main__` block; no tools yet
- [x] T006 Create `.mcp.json` at repo root — static MCP server config pointing to `python -m src.server` so the SDK auto-loads the server
- [x] T007 Create `pytest.ini` or `[tool.pytest.ini_options]` in `pyproject.toml` — set `asyncio_mode = "auto"` for `pytest-asyncio`

**Checkpoint**: Foundation ready — FastMCP server boots, MCP config registered, pytest async configured

---

## Phase 3: User Story 1 — Agent Invokes MCP Tool and Receives Result (Priority: P1) 🎯 MVP

**Goal**: Agent calls the `echo` tool on the `localsearch` MCP server with valid input and receives the structured `{file, start_line, end_line, snippet}` payload back — conforming to the constitution's mandated result schema.

**Independent Test**: Run `python -m src.agent "Use the echo tool to echo the message 'hello world'"` — agent should print a response referencing the `snippet` and `file` fields. Run `uv run pytest tests/unit/ tests/contract/` — all pass using real subprocess transport.

### Implementation for User Story 1

- [x] T008 [P] [US1] Add `echo` tool to `src/server/__main__.py` — typed `message: str` param, returns `{"file": "stdin", "start_line": 1, "end_line": 1, "snippet": message}` (constitution-mandated result schema), description ≤3 sentences, stderr-only logging
- [x] T009 [P] [US1] Create `src/agent/main.py` — `run(prompt: str) -> str` async function using `claude_agent_sdk.query()` with `ClaudeAgentOptions(mcp_servers={"localsearch": {...}}, allowed_tools=["mcp__localsearch__*"])`; check `SystemMessage(subtype="init")` for connection status (stub — error-raising behavior added in T015); extract `ResultMessage` for output (no `__main__` block — entry point is `src/agent/__main__.py`, added in T018)
- [x] T010 [US1] Implement `src/agent/__init__.py` — expose `run` for programmatic use (import from `main.py`)
- [x] T011 [US1] Verify FastMCP auto-validation rejects empty `message` string via `minLength: 1` in input schema — covered by T012's `is_error=True` test case; no standalone artifact needed (regression caught by real subprocess test)
- [x] T018 [US1] Add `src/agent/__main__.py` — entry point that calls `asyncio.run(run(sys.argv[1]))` and prints result; this is the SOLE entry point for `python -m src.agent` (Python routes `-m pkg` to `__main__.py`, not to `main.py`'s `if __name__` block); required for the Phase 3 checkpoint independent test
- [x] T012 [P] [US1] Write integration test `tests/unit/test_server_tools.py` — start MCP server as a real subprocess (real stdio transport, no fakes or in-memory clients): test `echo` returns all four result fields (`file`, `start_line`, `end_line`, `snippet`) for valid input, and returns `is_error=True` for empty string input
- [x] T013 [P] [US1] Write contract test `tests/contract/test_tool_schema.py` — start MCP server as a real subprocess, call `list_tools()` over stdio transport, and assert the returned tool schema for `echo` matches the `ToolInput`, `ToolResult`, and `ToolError` definitions in `contracts/tool-schema.json`; no static file comparison without a live server connection
- [x] T013b [US1] Add sequential tool call test to `tests/unit/test_server_tools.py` — call `echo` twice in sequence via real subprocess MCP client and verify each result maps to its input (covers FR-005; sequential guarantee documented in spec.md Assumptions)

**Checkpoint**: User Story 1 fully functional — `python -m src.agent` runs via `__main__.py` (T018), agent calls `echo`, receives result (`{file, start_line, end_line, snippet}`), subprocess-based tests pass

---

## Phase 4: User Story 2 — Agent Handles MCP Tool Call Failure Gracefully (Priority: P2)

**Goal**: Agent surfaces a clear, structured error for all failure modes (unavailable server, missing tool, bad input) — no silent hangs, no raw Python tracebacks.

**Independent Test**: Run `python -m src.agent "Call the tool called 'nonexistent' on the localsearch server"` — agent should report a tool-not-found error. Stop the server subprocess mid-run — agent should surface `CLIConnectionError` within timeout. Call `echo` with empty string — agent receives `-32602` error description.

### Implementation for User Story 2

- [x] T014 [US2] Update `src/agent/main.py` — catch `CLIConnectionError` and `ProcessError` from `claude_agent_sdk`; re-raise with human-readable message; enforce agent-level timeout (default 60s) via `asyncio.wait_for` or SDK option
- [x] T015 [US2] Update `src/agent/main.py` — check `SystemMessage(subtype="init")` for failed MCP server connections (`status != "connected"`); raise `RuntimeError` listing failed servers immediately (no silent pass-through)
- [x] T016 [P] [US2] Write integration test `tests/integration/test_agent_mcp.py` — subprocess end-to-end: (a) valid `echo` call succeeds and all four schema fields correct; (b) call to non-existent tool surfaces error; (c) empty-string input surfaces `-32602` error; (d) assert round-trip latency < 5s (SC-002) and commit baseline value as a comment in the test file

**Checkpoint**: User Story 2 fully functional — all three failure modes surface structured errors, integration tests pass

---

## Phase 5: User Story 3 — Developer Verifies Agent-MCP Integration End-to-End (Priority: P3)

**Goal**: A developer can follow `quickstart.md` from scratch, run three commands, and see the agent call `echo` with output visible in the terminal — setup to working demo in under 10 minutes (SC-004).

**Independent Test**: Follow `quickstart.md` step-by-step in a clean environment (`uv sync`, verify server starts, run agent, run `uv run pytest`). All steps succeed. Agent output clearly shows tool name `mcp__localsearch__echo` and result fields.

### Implementation for User Story 3

- [x] T017 [US3] Update `src/agent/__main__.py` (created in T018) — after `run()` returns, print the tool name called and result fields to stdout; `run()` in `main.py` MUST remain a pure function that returns a string (callers handle display); depends on T018
- [x] T019 [US3] Validate `quickstart.md` step 2 (server smoke test command) against actual `src/server/__main__.py` implementation — update command if server name or init output differs

**Checkpoint**: All three user stories independently functional; quickstart validated; full `uv run pytest` passes

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, observability, and final validation across all stories

- [x] T021 [P] Add stderr logging to `src/server/__main__.py` using `sys.stderr` — log each tool invocation name and result status (not payload) for observability; confirm no stdout pollution
- [x] T022 [P] Run `ruff check src/ tests/` and fix all violations (ruff config already in `pyproject.toml` from T002; this task enforces a clean lint pass before final commit)
- [x] T023 Run full `uv run pytest` — confirm all unit, contract, and integration tests pass; fix any failures
- [x] T024 Verify quickstart.md end-to-end in clean shell — confirm SC-004 (≤10 min setup) is met; update troubleshooting table if new failure modes discovered

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **User Story 1 (Phase 3)**: Depends on Phase 2 — MVP core capability
- **User Story 2 (Phase 4)**: Depends on Phase 3 (shares `src/agent/main.py`) — extends agent error handling
- **User Story 3 (Phase 5)**: Depends on Phase 3 — adds output formatting to `__main__.py` (T017, depends on T018 from Phase 3) and DX validation
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no story dependencies; fully independent
- **US2 (P2)**: After Phase 3 — modifies `src/agent/main.py` started in US1; independently testable via integration tests
- **US3 (P3)**: After Phase 3 — adds output formatting and `__main__.py` entry point; independently testable via quickstart

### Within Each User Story

- Server tool implementation (T008) and agent scaffold (T009) are parallel [P]
- Unit tests (T012) and contract tests (T013) are parallel [P] with each other and with T008/T009
- Agent error handling (T014, T015) depend on the working `run()` function from T009
- Integration tests (T016) depend on T008 + T009 + T014 + T015

### Parallel Opportunities

- T003 + T004 can run in parallel (different `__init__.py` files)
- T008 + T009 can run in parallel (different files: `server/__main__.py` vs `agent/main.py`)
- T012 + T013 can run in parallel (different test files)
- T017 depends on T018 (not parallel — T017 modifies the file T018 creates)
- T021 + T022 can run in parallel (different concerns)

---

## Parallel Example: User Story 1

```bash
# These tasks can run simultaneously (different files):
Task T008: "Add echo tool to src/server/__main__.py"
Task T009: "Create src/agent/main.py with query() loop"
Task T012: "Write subprocess integration tests in tests/unit/test_server_tools.py"
Task T013: "Write contract tests in tests/contract/test_tool_schema.py"

# Then sequentially:
Task T010: "Implement src/agent/__init__.py"
Task T011: "Add input validation to echo tool"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `python -m src.agent "Use echo tool with 'hello world'"` returns response with `snippet` and `file` fields; `uv run pytest tests/unit/ tests/contract/` passes
5. Demo ready

### Incremental Delivery

1. Phase 1 + 2 → Project scaffold boots, pytest configured
2. Phase 3 (US1) → Agent calls tool, gets result → **MVP demo ready**
3. Phase 4 (US2) → Error paths covered → integration tests pass
4. Phase 5 (US3) → Quickstart validated → SC-004 met
5. Phase 6 → Lint clean, full test suite green

### Suggested MVP Scope

**Phase 1 + Phase 2 + Phase 3 only** — 15 tasks total (T001–T018). This delivers the core capability (US1): agent calls `echo` via `python -m src.agent`, receives `{file, start_line, end_line, snippet}`, subprocess-based tests pass. No error-path hardening — that comes in US2.

---

## Notes

- [P] tasks = different files, no cross-task dependencies — safe to run simultaneously
- [Story] label maps each task to its user story for traceability
- **No `print()` in `src/server/`** — stdout is the MCP protocol stream; use `sys.stderr` exclusively
- **Tool naming**: server name `"localsearch"` + tool `echo` → fully-qualified `mcp__localsearch__echo`
- **FastMCP import**: tests start a real subprocess; server uses `from mcp.server.fastmcp import FastMCP`; no in-memory `Client(server)` usage (Principle VI)
- Commit after each phase checkpoint to preserve working state
- Stop at any checkpoint to validate independently before proceeding
