import sys
from contextlib import asynccontextmanager

import anyio
from mcp.server.fastmcp import FastMCP
from pydantic import Field

import src.server.monitor as _monitor


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
