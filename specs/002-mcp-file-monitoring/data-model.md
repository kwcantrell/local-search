# Data Model: MCP File Monitoring

**Feature**: 002-mcp-file-monitoring
**Phase**: 1 output
**Date**: 2026-03-20

---

## Entities

### MonitoredEntry

Represents a file or directory path registered by the agent for tracking.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `path` | `str` | absolute, exists at registration time | Normalized via `os.path.abspath` |
| `kind` | `Literal["file", "dir"]` | required | `"dir"` triggers `recursive=True` in watchdog |
| `registered_at` | `float` | Unix timestamp (`time.time()`) | Set at registration; immutable |

**Registry**: `dict[str, MonitoredEntry]` keyed by `path`. Server-global singleton. Mutated only by async tool handlers on the event loop thread.

**Validation rules**:
- `path` must pass `os.path.exists()` at registration time; rejected otherwise with a descriptive error message.
- Duplicate registrations are silently deduplicated — second registration of an existing path returns `"already_monitored"` status without creating a new watcher.

---

### ChangeEvent

A record of a debounced file system change, stored in the event buffer and returned by `poll_events`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `path` | `str` | absolute path of affected file | May differ from registered path if a directory was registered and an interior file changed |
| `event_type` | `Literal["created", "modified", "deleted", "moved"]` | required | Mapped from watchdog event class names |
| `timestamp` | `float` | Unix timestamp | Set when the debounce window closes and the event is flushed to the buffer |

**Event buffer**: `collections.deque[ChangeEvent]` with `maxlen=1000`. Server-global singleton. Written only by the async debounce task; read by the `poll_events` tool handler.

**Coalescing rule**: Within a debounce window, multiple events for the same `path` are merged by keeping the latest `event_type` (last-write-wins). If the sequence is `modified → modified → deleted`, the delivered event type is `"deleted"`. This satisfies SC-004.

---

### RawEvent (internal)

An unprocessed watchdog event sent from the Observer thread to the debounce task via `MemoryObjectSendStream`. Not exposed in tool responses.

| Field | Type | Notes |
|---|---|---|
| `src_path` | `str` | From `watchdog.events.FileSystemEvent.src_path` |
| `event_type` | `str` | Watchdog event class → mapped type |

**Mapping** (watchdog class → `event_type` string):

| watchdog class | `event_type` |
|---|---|
| `FileCreatedEvent` | `"created"` |
| `FileModifiedEvent` | `"modified"` |
| `FileDeletedEvent` | `"deleted"` |
| `FileMovedEvent` | `"moved"` |
| `DirCreatedEvent` | `"created"` (dir) |
| `DirDeletedEvent` | `"deleted"` (dir) |
| `DirMovedEvent` | `"moved"` (dir) |

Directory events are included only when a directory entry is directly registered (not its parent).

---

## Server-Global State

All state lives in-process. Nothing is persisted to disk. State is lost on server restart (by design per spec assumptions).

```
_registry: dict[str, MonitoredEntry]      # path → MonitoredEntry
_event_buffer: deque[dict]                # chronological ChangeEvent dicts, maxlen=1000
_send_stream: MemoryObjectSendStream      # watchdog thread → debounce task
_recv_stream: MemoryObjectReceiveStream   # debounce task reads from
_observer: watchdog.Observer              # background thread, started at server init
```

**Access discipline**:
- `_registry` and `_event_buffer`: async event loop thread only (tool handlers + debounce task).
- `_send_stream.send_nowait()`: called from watchdog Observer thread (GIL-safe).
- `_observer`: started once at server startup (lifespan); stopped at server shutdown.

---

## State Transitions

### Monitoring lifecycle for a path

```
[not registered]
      │  register_files([path])  →  path exists
      ▼
[registered]  ──────────────────  watchdog.Observer.schedule(handler, path)
      │  file changes
      ▼
[RawEvent sent via send_nowait]
      │  debounce window expires
      ▼
[ChangeEvent flushed to _event_buffer]
      │  agent calls poll_events(since_ts)
      ▼
[ChangeEvent returned in response]
      │  deregister_files([path])
      ▼
[not registered]  ──────────────  watchdog watch cancelled/removed
```

### Debounce window state

```
[idle]  ←──── window expires, buffer flushed ────┐
   │                                              │
   │  first RawEvent for path                     │
   ▼                                              │
[window open: deadline = now + DEBOUNCE_WINDOW]   │
   │                                              │
   │  more RawEvents for same path                │
   ▼                                              │
[pending dict updated (last-write-wins)] ─────────┘
```

---

## Tool Response Schemas

### `register_files` response

```json
{
  "registered": ["<path>", ...],
  "already_monitored": ["<path>", ...],
  "errors": [
    {"path": "<path>", "reason": "<descriptive error>"},
    ...
  ]
}
```

### `deregister_files` response

```json
{
  "deregistered": ["<path>", ...],
  "not_monitored": ["<path>", ...]
}
```

### `list_monitored` response

```json
{
  "monitored": [
    {"path": "<path>", "kind": "file|dir", "registered_at": 1234567890.123},
    ...
  ]
}
```

### `poll_events` response

```json
{
  "events": [
    {"path": "<path>", "event_type": "created|modified|deleted|moved", "timestamp": 1234567890.456},
    ...
  ],
  "count": 3
}
```

Fields are never omitted or null (Constitution: Technical Standards — result schema). The `count` field allows the agent to detect non-empty results without inspecting the array.
