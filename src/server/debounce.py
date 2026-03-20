"""Debounce pipeline module for MCP file monitoring server.

Reads raw file system events from the shared memory object stream, coalesces
rapid events for the same path within a configurable time window
(DEBOUNCE_WINDOW_SECS, default 0.5s), and flushes ChangeEvent records into
the shared event buffer. Events for paths not in the registry are filtered out.
"""

import os
import time

import anyio

DEBOUNCE_WINDOW_SECS: float = float(os.environ.get("DEBOUNCE_WINDOW_SECS", "0.5"))


async def debounce_task() -> None:
    """Consume raw events from _recv_stream, coalesce per-path, flush to _event_buffer.

    Uses a rolling deadline: after the first event arrives, waits up to
    DEBOUNCE_WINDOW_SECS for more events on the same path before flushing.
    Last-write-wins coalescing: if multiple event types arrive for the same path
    within the window, the latest one is kept.
    """
    from src.server.monitor import _event_buffer, _recv_stream, _registry

    pending: dict[str, str] = {}  # path → latest event_type within window

    while True:
        # Wait for the first event (blocking receive)
        try:
            raw = await _recv_stream.receive()
        except anyio.EndOfStream:
            break

        pending[raw["src_path"]] = raw["event_type"]

        # Drain additional events within the debounce window (rolling deadline)
        with anyio.move_on_after(DEBOUNCE_WINDOW_SECS):
            while True:
                try:
                    raw = await _recv_stream.receive()
                    pending[raw["src_path"]] = raw["event_type"]
                except anyio.EndOfStream:
                    break

        # Flush coalesced events — filter paths not in registry
        flush_time = time.time()
        for path, event_type in pending.items():
            if path not in _registry:
                # Check if path is under a registered directory
                matched = False
                for reg_path, entry in _registry.items():
                    if entry.kind == "dir" and path.startswith(reg_path + os.sep):
                        matched = True
                        break
                if not matched:
                    continue
            _event_buffer.append(
                {"path": path, "event_type": event_type, "timestamp": flush_time}
            )

        pending.clear()
