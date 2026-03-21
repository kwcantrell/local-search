# MCP Tool Contracts: File Monitoring

**Feature**: 002-mcp-file-monitoring
**Transport**: stdio (JSONRPC line-delimited)
**Server**: FastMCP (`src/server/__main__.py`)

---

## Tool: `register_files`

**Description**: Register one or more file or directory paths for monitoring. Invalid or non-existent paths are reported per-path without rejecting the whole list. Duplicate paths are deduplicated silently.

**Parameters**:

| Name | Type | Required | Description |
|---|---|---|---|
| `paths` | `list[str]` | yes | Absolute or relative paths to files or directories. Min 1 item. |

**Returns**: `dict` with three keys (all always present):

```json
{
  "registered": ["<path>", ...],
  "already_monitored": ["<path>", ...],
  "errors": [
    {"path": "<path>", "reason": "<string>"}
  ]
}
```

**Behaviour**:
- Each path is normalized via `os.path.abspath`.
- If `os.path.exists(path)` is `False`, the path is added to `errors` with reason `"path does not exist"`.
- If the path is already registered, it is added to `already_monitored`; no new watcher is created.
- Valid, new paths are added to `registered` and a watchdog schedule is started.
- Directories trigger `recursive=True` watching.

**Error conditions** (MCP structured error response):
- Empty `paths` list → MCP error `INVALID_PARAMS`.

---

## Tool: `deregister_files`

**Description**: Remove one or more paths from monitoring. Paths not currently monitored are acknowledged without error.

**Parameters**:

| Name | Type | Required | Description |
|---|---|---|---|
| `paths` | `list[str]` | yes | Paths to stop monitoring. Min 1 item. |

**Returns**:

```json
{
  "deregistered": ["<path>", ...],
  "not_monitored": ["<path>", ...]
}
```

**Behaviour**:
- Each path is normalized via `os.path.abspath`.
- If the path is in the registry, it is removed and its watchdog watch is cancelled.
- If the path is not in the registry, it is added to `not_monitored` (no error).

**Error conditions**:
- Empty `paths` list → MCP error `INVALID_PARAMS`.

---

## Tool: `list_monitored`

**Description**: Return the current list of all paths registered for monitoring. Returns an empty list if nothing is registered.

**Parameters**: none

**Returns**:

```json
{
  "monitored": [
    {
      "path": "<absolute path>",
      "kind": "file",
      "registered_at": 1234567890.123
    }
  ]
}
```

`kind` is `"file"` or `"dir"`. `registered_at` is a Unix float timestamp. The list is unordered.

**Error conditions**: none (always succeeds; returns `{"monitored": []}` when empty).

---

## Tool: `poll_events`

**Description**: Return all file change events that occurred after the given timestamp. Call this repeatedly to drain the event stream. Pass `since_ts=0.0` on first call to receive all buffered events.

**Parameters**:

| Name | Type | Required | Description |
|---|---|---|---|
| `since_ts` | `float` | yes | Unix timestamp. Events with `timestamp > since_ts` are returned. Use `0.0` on first call. |

**Returns**:

```json
{
  "events": [
    {
      "path": "<absolute path>",
      "event_type": "modified",
      "timestamp": 1234567890.456
    }
  ],
  "count": 1
}
```

`event_type` is one of: `"created"`, `"modified"`, `"deleted"`, `"moved"`.
`count` equals `len(events)`.
Events are returned in ascending timestamp order.

**Agent usage pattern**:
```
last_ts = 0.0
loop:
    result = poll_events(since_ts=last_ts)
    if result["count"] > 0:
        last_ts = max(e["timestamp"] for e in result["events"])
        # process events
    sleep N seconds
```

**Error conditions**: none (returns `{"events": [], "count": 0}` when no new events).

---

## Constitution compliance notes

- All tool descriptions are ≤ 3 sentences, informative, free of marketing language (Principle IV).
- All response fields are always present and non-null (Technical Standards — result schema).
- No blocking I/O in tool handlers; watchdog runs in its Observer thread (Principles III, VI).
- Tool parameters are self-documenting (Principle IV).
