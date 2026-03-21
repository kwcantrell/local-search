# Quickstart: MCP File Monitoring

**Feature**: 002-mcp-file-monitoring

---

## Prerequisites

```bash
# From repo root
pip install -e ".[dev]"
pip install watchdog>=4.0
```

Or add `watchdog>=4.0` to `pyproject.toml` dependencies and re-run `pip install -e ".[dev]"`.

---

## Run the MCP server standalone

```bash
cd /workspace
python -m src.server
```

The server speaks MCP over stdio and exits when stdin closes.

---

## Run the agent (interactive)

```bash
cd /workspace/src
python -m agent "Register /tmp/testfile.txt for monitoring, then poll for changes every 5 seconds for 30 seconds."
```

---

## Run tests

```bash
cd /workspace
pytest tests/ -v
```

All tests are end-to-end: they start a real MCP server subprocess, connect through the MCP transport, perform real file I/O, and verify real notifications. No mocks.

---

## Typical agent interaction flow

```
Agent → register_files(paths=["/tmp/foo.txt", "/tmp/bar/"])
Server → {"registered": ["/tmp/foo.txt", "/tmp/bar"], "already_monitored": [], "errors": []}

# ... time passes, files change ...

Agent → poll_events(since_ts=0.0)
Server → {"events": [{"path": "/tmp/foo.txt", "event_type": "modified", "timestamp": 1711234567.89}], "count": 1}

Agent → poll_events(since_ts=1711234567.89)
Server → {"events": [], "count": 0}

Agent → list_monitored()
Server → {"monitored": [{"path": "/tmp/foo.txt", "kind": "file", "registered_at": 1711234560.0}, {"path": "/tmp/bar", "kind": "dir", "registered_at": 1711234560.1}]}

Agent → deregister_files(paths=["/tmp/foo.txt"])
Server → {"deregistered": ["/tmp/foo.txt"], "not_monitored": []}
```

---

## Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `DEBOUNCE_WINDOW_SECS` | `0.5` | Seconds to wait after first event before flushing a coalesced notification |
| `EVENT_BUFFER_MAXLEN` | `1000` | Maximum number of ChangeEvents held in the in-memory buffer |
| `EVENT_QUEUE_MAXSIZE` | `256` | Maximum raw events in the watchdog→asyncio bridge queue (drop on overflow) |

---

## Project structure (after implementation)

```
src/
└── server/
    ├── __init__.py
    ├── __main__.py       # FastMCP app, lifespan (observer + debounce task start/stop)
    ├── monitor.py        # MonitoredEntry registry, watchdog handler, ChangeEvent buffer
    └── debounce.py       # async debounce task consuming from MemoryObjectStream

tests/
├── contract/
│   └── test_tool_schema.py    # Validates tool input/output schema against contracts/mcp-tools.md
├── integration/
│   ├── test_register.py       # US1: register + deregister + list (real MCP subprocess)
│   ├── test_notifications.py  # US2: file change → poll_events delivery (real file I/O)
│   └── test_deregister.py     # US3: deregister stops notifications (real file I/O)
└── unit/
    └── test_debounce.py       # Debounce logic only (real asyncio, no mocks)
```
