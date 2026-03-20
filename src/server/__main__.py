import os
import sys
import time
from contextlib import asynccontextmanager

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.types import INVALID_PARAMS
from pydantic import Field

import src.server.monitor as _monitor
from src.server.monitor import McpFileHandler, MonitoredEntry


@asynccontextmanager
async def lifespan(app):
    """Start watchdog observer and debounce task; stop them on shutdown."""
    from src.server.debounce import debounce_task
    from watchdog.observers import Observer

    # Reset global state for clean startup (important in test environments)
    _monitor._registry.clear()
    _monitor._event_buffer.clear()

    # Reinitialize streams and observer each time (threads/streams can only be used once)
    import anyio as _anyio
    send, recv = _anyio.create_memory_object_stream(
        max_buffer_size=_monitor.EVENT_QUEUE_MAXSIZE
    )
    _monitor._send_stream = send
    _monitor._recv_stream = recv

    observer = Observer()
    _monitor._observer = observer
    observer.start()
    async with anyio.create_task_group() as tg:
        tg.start_soon(debounce_task)
        yield
        tg.cancel_scope.cancel()

    observer.stop()
    observer.join()


mcp = FastMCP("localsearch", lifespan=lifespan)


@mcp.tool()
def echo(message: str = Field(..., min_length=1)) -> dict:
    """Echo the input message back with a status field.

    Returns a dict with 'result' (the echoed message) and 'status' ('ok').
    Requires a non-empty message string.
    """
    print("tool=echo status=ok", file=sys.stderr)
    return {"result": message, "status": "ok"}


@mcp.tool()
def register_files(paths: list[str]) -> dict:
    """Register one or more file or directory paths for monitoring.

    Invalid or non-existent paths are reported per-path without rejecting the whole list.
    Duplicate paths are deduplicated silently.
    """
    if not paths:
        from mcp.shared.exceptions import McpError
        raise McpError(INVALID_PARAMS, "paths must contain at least one entry")

    registered = []
    already_monitored = []
    errors = []

    for raw_path in paths:
        path = os.path.abspath(raw_path)
        if path in _monitor._registry:
            already_monitored.append(path)
            continue
        if not os.path.exists(path):
            errors.append({"path": path, "reason": "path does not exist"})
            continue
        kind = "dir" if os.path.isdir(path) else "file"
        handler = McpFileHandler()
        watch = _monitor._observer.schedule(handler, path, recursive=(kind == "dir"))
        entry = MonitoredEntry(path=path, kind=kind, registered_at=time.time(), watch=watch)
        _monitor._registry[path] = entry
        registered.append(path)

    return {"registered": registered, "already_monitored": already_monitored, "errors": errors}


@mcp.tool()
def list_monitored() -> dict:
    """Return the current list of all paths registered for monitoring.

    Returns an empty list if nothing is registered.
    """
    return {
        "monitored": [
            {"path": e.path, "kind": e.kind, "registered_at": e.registered_at}
            for e in _monitor._registry.values()
        ]
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
