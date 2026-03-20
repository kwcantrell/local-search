---

description: "Task list for MCP File Monitoring feature implementation"
---

# Tasks: MCP File Monitoring

**Input**: Design documents from `/specs/002-mcp-file-monitoring/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/mcp-tools.md ✅, quickstart.md ✅

**Tests**: End-to-end integration tests using real MCP subprocess + real file I/O. No mocks (prohibited by constitution and project policy).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths included in all task descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add `watchdog` dependency and create the two new server modules needed by all user stories.

- [X] T001 Add `watchdog>=4.0` to `pyproject.toml` dependencies
- [X] T002 [P] Create `src/server/monitor.py` — empty module with module-level docstring
- [X] T003 [P] Create `src/server/debounce.py` — empty module with module-level docstring

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story can be implemented. Implements global server state, watchdog bridge, and debounce pipeline — shared by all four tool handlers.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Implement `MonitoredEntry` dataclass and `ChangeEvent` dataclass in `src/server/monitor.py` (fields: `path`, `kind`, `registered_at` for MonitoredEntry; `path`, `event_type`, `timestamp` for ChangeEvent per data-model.md)
- [X] T005 Implement server-global state singletons in `src/server/monitor.py`: `_registry: dict[str, MonitoredEntry]`, `_event_buffer: deque[dict]` (maxlen from `EVENT_BUFFER_MAXLEN` env var, default 1000), `_send_stream`, `_recv_stream` (anyio MemoryObjectStream pair, capacity from `EVENT_QUEUE_MAXSIZE` env var, default 256), `_observer: watchdog.Observer`
- [X] T006 Implement `McpFileHandler(FileSystemEventHandler)` in `src/server/monitor.py` — `on_any_event` maps watchdog event classes to `event_type` strings per data-model.md mapping table and calls `_send_stream.send_nowait(RawEvent(src_path, event_type))`, dropping on `WouldBlock`
- [X] T007 Implement async debounce task in `src/server/debounce.py`: reads from `_recv_stream`, coalesces events per path using `dict[str, str]` (last-write-wins), uses `anyio.fail_after(DEBOUNCE_WINDOW_SECS)` rolling deadline, flushes `ChangeEvent` dicts to `_event_buffer` when window closes; filters out events for paths not in `_registry`; reads `DEBOUNCE_WINDOW_SECS` env var (default 0.5)
- [X] T008 Add `lifespan` context manager to `src/server/__main__.py`: starts `watchdog.Observer`, spawns debounce task via `anyio.create_task_group`, stops observer and cancels task group on exit; wire up FastMCP app to use this lifespan

**Checkpoint**: Foundation ready — global state, watchdog bridge, and debounce pipeline exist. User story tool implementations can now begin.

---

## Phase 3: User Story 1 — Register Files for Monitoring (Priority: P1) 🎯 MVP

**Goal**: Agent submits file/directory paths; server validates, deduplicates, starts watching, and returns structured confirmation.

**Independent Test**: Start real MCP subprocess, call `register_files` with valid + invalid + duplicate paths, assert response keys (`registered`, `already_monitored`, `errors`) and that `list_monitored` shows the registered paths. No file changes required.

### Tests for User Story 1

- [X] T009 [P] [US1] Add contract schema tests for `register_files` and `list_monitored` tools in `tests/contract/test_tool_schema.py` — verify tool names, parameter types (`paths: list[str]`), and required response keys against contracts/mcp-tools.md
- [X] T010 [P] [US1] Write integration tests in `tests/integration/test_register.py`: test valid path registration, invalid path reporting (path does not exist → appears in `errors`), duplicate path deduplication (second call → `already_monitored`), and empty-list error (`INVALID_PARAMS`)

### Implementation for User Story 1

- [X] T011 [US1] Implement `register_files(paths: list[str])` tool in `src/server/__main__.py`: normalize each path via `os.path.abspath`, check `os.path.exists`, reject empty list with `INVALID_PARAMS` MCP error, add valid new paths to `_registry` (create `MonitoredEntry`), schedule `watchdog.Observer.schedule(McpFileHandler(), path, recursive=kind=="dir")`, return `{"registered": [...], "already_monitored": [...], "errors": [...]}`
- [X] T012 [US1] Implement `list_monitored()` tool in `src/server/__main__.py`: return `{"monitored": [{"path": e.path, "kind": e.kind, "registered_at": e.registered_at} for e in _registry.values()]}`

**Checkpoint**: User Story 1 is fully functional. `register_files` + `list_monitored` work end-to-end via real MCP subprocess. Run `tests/integration/test_register.py` to validate independently.

---

## Phase 4: User Story 2 — Receive File Change Notifications (Priority: P2)

**Goal**: After registering a file, the agent calls `poll_events(since_ts)` and receives debounced `ChangeEvent` records for file modifications, creations, deletions, and moves.

**Independent Test**: Start real MCP subprocess, register a temp file, trigger a file write, wait > debounce window (0.5s), call `poll_events(since_ts=0.0)`, assert at least one event with correct `path` and `event_type`. For debounce: trigger 50 rapid writes within window, assert `count == 1`.

### Tests for User Story 2

- [ ] T013 [P] [US2] Add contract schema test for `poll_events` tool in `tests/contract/test_tool_schema.py` — verify `since_ts: float` parameter and response keys (`events`, `count`) per contracts/mcp-tools.md
- [ ] T014 [P] [US2] Write integration tests in `tests/integration/test_notifications.py`: test file modify → notification received within 2s (SC-002); file delete → deletion event; 50 rapid writes within debounce window → exactly 1 coalesced event (SC-004); `poll_events(since_ts=last_ts)` → no duplicate events

### Implementation for User Story 2

- [ ] T015 [US2] Implement `poll_events(since_ts: float)` tool in `src/server/__main__.py`: scan `_event_buffer` for events with `timestamp > since_ts`, return `{"events": [...], "count": N}` with events sorted by ascending timestamp; always return both keys even when empty

**Checkpoint**: User Story 2 fully functional. File changes flow from watchdog → bridge → debounce → buffer → `poll_events`. Run `tests/integration/test_notifications.py` to validate independently.

---

## Phase 5: User Story 3 — Deregister Files from Monitoring (Priority: P3)

**Goal**: Agent removes specific paths from the monitored list; server cancels the watchdog watch and confirms removal. Paths not currently monitored are acknowledged gracefully.

**Independent Test**: Start real MCP subprocess, register a temp file, deregister it, trigger a file write, wait > debounce window, call `poll_events(since_ts=0.0)`, assert `count == 0`. Also test deregistering an unmonitored path → `not_monitored` key present, no error.

### Tests for User Story 3

- [ ] T016 [P] [US3] Add contract schema test for `deregister_files` tool in `tests/contract/test_tool_schema.py` — verify `paths: list[str]` parameter and response keys (`deregistered`, `not_monitored`)
- [ ] T017 [P] [US3] Write integration tests in `tests/integration/test_deregister.py`: test deregister stops notifications (file change after deregister → no event); test deregister of unknown path → `not_monitored` list, no MCP error; test deregister then re-register same path works correctly

### Implementation for User Story 3

- [ ] T018 [US3] Implement `deregister_files(paths: list[str])` tool in `src/server/__main__.py`: normalize each path via `os.path.abspath`, reject empty list with `INVALID_PARAMS`; for each path in `_registry` cancel the watchdog watch (`_observer.unschedule(watch)`) and remove from `_registry`; paths not in registry go to `not_monitored`; return `{"deregistered": [...], "not_monitored": [...]}`

**Checkpoint**: User Story 3 fully functional. Deregistration stops watchdog watch and prevents future events. Run `tests/integration/test_deregister.py` independently.

---

## Phase 6: User Story 4 — Query Monitored File List (Priority: P4)

**Goal**: Agent can retrieve the current complete list of monitored paths with metadata at any time.

**Independent Test**: Register several paths, call `list_monitored()`, verify returned list matches registered paths with correct `kind` and `registered_at` values. Call `list_monitored()` with empty registry → `{"monitored": []}`.

> **Note**: `list_monitored` tool is implemented in Phase 3 (T012) as it is needed to verify US1 registration. This phase covers its dedicated test coverage and the empty-list edge case.

### Tests for User Story 4

- [ ] T019 [P] [US4] Write integration tests in `tests/integration/test_register.py` (extend existing file): test `list_monitored` returns all registered paths after multiple registrations; test `list_monitored` returns empty list when nothing registered; test `kind` field is `"file"` for files and `"dir"` for directories

**Checkpoint**: User Story 4 validated. `list_monitored` handles both populated and empty registries correctly.

---

## Phase 7: Unit Test — Debounce Logic

**Purpose**: Validate debounce algorithm directly without MCP subprocess overhead. Uses real asyncio + anyio MemoryObjectStream. No mocks.

- [ ] T020 Write `tests/unit/test_debounce.py`: test that N rapid events for the same path within debounce window produce exactly 1 `ChangeEvent` in `_event_buffer` (SC-004); test last-write-wins coalescing (`modified → deleted` → event_type is `"deleted"`); test that events for unregistered paths are filtered out; test that idle debounce task does not spin (no spurious flushes)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Environment variable configuration, linting, quickstart validation.

- [ ] T021 [P] Verify `DEBOUNCE_WINDOW_SECS`, `EVENT_BUFFER_MAXLEN`, `EVENT_QUEUE_MAXSIZE` env vars are read at module import time in `src/server/debounce.py` and `src/server/monitor.py` with correct defaults (0.5, 1000, 256) per quickstart.md
- [ ] T022 [P] Run `ruff check src/ tests/` and fix all lint errors
- [ ] T023 Run full test suite `pytest tests/ -v` from `/workspace` and confirm all tests pass
- [ ] T024 Validate quickstart.md scenarios manually: start server standalone (`python -m src.server`), run agent with file monitoring prompt, verify `register_files` → file change → `poll_events` round-trip works end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Phase 2 — no other story dependencies
- **US2 (Phase 4)**: Depends on Phase 2 — no US1 dependency (debounce pipeline already complete)
- **US3 (Phase 5)**: Depends on Phase 2 — no US1/US2 dependency
- **US4 (Phase 6)**: Depends on T012 from Phase 3 (implementation already done) — test-only phase
- **Unit Tests (Phase 7)**: Depends on Phase 2 (debounce task) — can run after T007
- **Polish (Phase 8)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no cross-story deps
- **US2 (P2)**: Can start after Phase 2 — no cross-story deps (poll_events is independent of register/deregister)
- **US3 (P3)**: Can start after Phase 2 — deregister uses same registry/observer as US1 but implements a separate tool
- **US4 (P4)**: Implementation complete in US1 (T012); Phase 6 is test-only validation

### Within Each User Story

- Contract tests [P] and integration tests [P] can be written in parallel (different files)
- Implementation tasks depend on Foundational phase (T004–T008) being complete
- Tests should be written and verified to fail before implementation

### Parallel Opportunities

- T002 and T003 (Phase 1): parallel — different files
- T009 and T010 (US1 tests): parallel — different files
- T013 and T014 (US2 tests): parallel — different files
- T016 and T017 (US3 tests): parallel — different files
- T021 and T022 (Polish): parallel — different concerns
- Once Phase 2 is complete: US1, US2, US3 can proceed in parallel

---

## Parallel Example: User Story 1

```bash
# Write both test files simultaneously (no file conflicts):
Task T009: "Add contract schema tests for register_files and list_monitored in tests/contract/test_tool_schema.py"
Task T010: "Write integration tests in tests/integration/test_register.py"

# Then implement (single file, sequential):
Task T011: "Implement register_files tool in src/server/__main__.py"
Task T012: "Implement list_monitored tool in src/server/__main__.py"
```

## Parallel Example: User Story 2

```bash
# Write both test files simultaneously:
Task T013: "Add contract schema test for poll_events in tests/contract/test_tool_schema.py"
Task T014: "Write integration tests in tests/integration/test_notifications.py"

# Then implement:
Task T015: "Implement poll_events tool in src/server/__main__.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T003)
2. Complete Phase 2: Foundational (T004–T008) — **CRITICAL, blocks everything**
3. Complete Phase 3: User Story 1 (T009–T012)
4. **STOP and VALIDATE**: `pytest tests/integration/test_register.py -v`
5. Agent can now register files and query the monitored list

### Incremental Delivery

1. Setup + Foundational → watchdog pipeline running
2. US1 → `register_files` + `list_monitored` working → **MVP demo ready**
3. US2 → `poll_events` working → full monitoring loop functional
4. US3 → `deregister_files` working → full lifecycle management
5. US4 tests → `list_monitored` edge cases validated
6. Unit tests + Polish → production-ready

### Parallel Team Strategy

With multiple developers (after Phase 2 complete):
- Developer A: US1 (T009–T012)
- Developer B: US2 (T013–T015)
- Developer C: US3 (T016–T018)

All three user story phases touch `src/server/__main__.py` (different tools) — coordinate to avoid merge conflicts or work sequentially.

---

## Notes

- [P] tasks = different files, no blocking dependencies — safe to run in parallel
- [Story] label maps each task to its user story for traceability
- All tests are end-to-end against real MCP subprocess + real file I/O — no mocks (prohibited)
- `src/server/__main__.py` is the single file where all four tool handlers live — sequential work to avoid conflicts
- `src/server/monitor.py` and `src/server/debounce.py` are new files (clean slate)
- Existing `tests/contract/test_tool_schema.py` is extended (not replaced) in T009/T013/T016
- Existing `tests/integration/test_agent_mcp.py` is preserved unchanged (echo tool tests)
- Commit after each task or logical group; each checkpoint is a valid stopping point
