# Research: MCP File Monitoring

**Feature**: 002-mcp-file-monitoring
**Phase**: 0 — all NEEDS CLARIFICATION resolved
**Date**: 2026-03-20

---

## Decision 1: Notification delivery mechanism

**Decision**: Polling tool pattern — agent calls `poll_events(since_ts)` which returns a batch of accumulated change events.

**Rationale**: The claude-agent-sdk bridges MCP through the Claude CLI and routes only three methods: `initialize`, `tools/list`, `tools/call`. Progress notifications, resource subscription notifications, and experimental task events are not surfaced to the Python application. FastMCP has no async-generator/streaming tool call support — each tool call is a single `await fn(...)` returning one result. The only reliable server-to-agent delivery mechanism through this SDK stack is a plain tool call that returns a list.

**Alternatives considered**:
- `ctx.report_progress()` — sends `notifications/progress` over stdio, but the claude-agent-sdk consumes these in the CLI layer and never yields them to the application's message iterator.
- MCP resource subscriptions (`session.send_resource_updated`) — FastMCP does not expose resource subscription registration (`subscribe=False` in capabilities); would require dropping to the low-level `mcp.server.lowlevel.server.Server` and is not routed by the SDK anyway.
- Long-running blocking tool — stdio transport is line-delimited JSONRPC; a tool handler cannot stream partial results mid-execution.
- Experimental task system — only `initialize`, `tools/list`, `tools/call` are routed by the SDK's MCP bridge.

**Implementation consequence**: The server exposes a `poll_events` tool. The agent is instructed via its system prompt to call this tool on a schedule (e.g., every N seconds) after registering files. The tool returns all events accumulated since the given timestamp. This is stateless from the agent's perspective (just pass the last-seen timestamp) and correct — no events are dropped as long as the server buffers them.

---

## Decision 2: watchdog-to-asyncio bridge

**Decision**: `watchdog.Observer` runs in its own thread (its normal mode). The `FileSystemEventHandler.on_any_event` callback calls `anyio.MemoryObjectSendStream.send_nowait()` to push raw events into a bounded in-process queue.

**Rationale**: `send_nowait` is safe from non-asyncio threads under CPython's GIL — it appends to a `deque` and sets an `Event`, both GIL-protected. This avoids blocking the Observer thread (which processes all OS events serially). `anyio.from_thread.BlockingPortal.call()` would block the Observer thread until the coroutine completes, risking event buildup under high file-change rates.

**Stream capacity**: 256 events (configurable). On overflow, the oldest/newest event is dropped with a logged warning. The debounce window reduces effective queue pressure significantly.

**Alternatives considered**:
- `loop.call_soon_threadsafe` (stdlib asyncio) — works but anyio's `send_nowait` is simpler and avoids importing the loop directly.
- `anyio.from_thread.run()` (blocking) — correct but blocks the Observer thread; inadvisable for high-frequency events.

---

## Decision 3: Debounce algorithm

**Decision**: Single async debounce task consuming from `MemoryObjectReceiveStream`. Uses a `dict[str, str]` (path → latest event type) as the pending buffer and `anyio.fail_after` with a rolling deadline from first-event-in-window.

**Rationale**: One task handles all paths. Rolling window (starts on first event arrival, not a fixed tick) avoids unnecessary wakeups. `anyio.fail_after` has correct anyio-native cancellation semantics. Dict coalescing (last-write-wins) satisfies SC-004: during a burst of N rapid changes, exactly one notification is delivered per debounce window per file.

**Window duration**: 0.5 seconds default, configurable via `DEBOUNCE_WINDOW_SECS` env var.

**Alternatives considered**:
- One asyncio task per monitored file — O(N) tasks for N files; wasteful for SC-003's 500-file target.
- Fixed-interval ticker — wakes even when no events are flowing; less efficient.
- `asyncio.sleep` polling loop — burns CPU and has imprecise timing.

---

## Decision 4: Global shared registry thread-safety

**Decision**: Registry (`set[str]`) is owned exclusively by the async event loop. The watchdog Observer thread has zero access to it — it only calls `send_nowait` on the stream. The debounce task filters events against `_monitored` before enqueuing them for `poll_events`. All mutations to `_monitored` occur in async tool handlers.

**Rationale**: Eliminates the thread-safety problem entirely. No locks needed. Simpler code. Iteration over `_monitored` during debounce filtering is safe because it only happens on the event loop thread.

**Alternatives considered**:
- `threading.Lock` protecting the set — acceptable for brief critical sections in async code, but unnecessary if the watchdog thread never touches the registry.
- `anyio.Lock` — async-only, cannot be acquired from the watchdog thread; ruled out.

---

## Decision 5: watchdog path for file vs. directory

**Decision**: Each registered path gets its own `watchdog.Observer.schedule(handler, path, recursive=True_if_dir)`. Files are registered with `recursive=False`; directories with `recursive=True`. The `FileSystemEventHandler` filters events to only pass through paths that are in `_monitored` (for file entries) or are children of a monitored directory.

**Rationale**: watchdog natively handles both files and directories. Scheduling them separately with the correct `recursive` flag gives the most precise event filtering. The `MonitoredEntry` record tracks whether a path is a file or directory so filtering can apply the correct rule.

**Path validation**: At registration time, `os.path.exists` is checked synchronously (brief, non-blocking for local file systems). Paths that do not exist are rejected with a descriptive error; the rest are registered. This satisfies FR-002 and SC-006.

---

## Decision 6: Event buffer for poll_events

**Decision**: A server-global `collections.deque(maxlen=MAX_EVENTS)` stores debounced `ChangeEvent` dicts (path, event_type, timestamp). `poll_events(since_ts: float) -> list[dict]` returns all events with `timestamp > since_ts`. Max buffer: 1000 events (configurable).

**Rationale**: Simple O(N) scan over a short deque is correct for this scale. No persistence needed (assumption: monitoring state lost on restart). The deque's `maxlen` prevents unbounded memory growth if the agent stops polling.

**Alternatives considered**:
- Per-file queues — unnecessary complexity for the access pattern (always query by timestamp, not by path).
- SQLite in-process — over-engineering for ephemeral in-memory events.

---

## Resolved clarifications from spec

| Question | Answer |
|---|---|
| Push vs. polling | Polling tool (see Decision 1) |
| Debounce | Rolling-window dict coalescer (Decision 3) |
| File-watching library | `watchdog` with anyio bridge (Decision 2) |
| Shared vs. per-session registry | Global shared set (Decision 4) |
| Files vs. directories | Both, separate watch schedules (Decision 5) |

---

## Dependencies to add

| Package | Version | Justification |
|---|---|---|
| `watchdog` | `>=4.0` | File system event detection; cross-platform; callback-based; background thread native |

`anyio` is already a transitive dependency of `mcp`. No other new third-party packages required.
