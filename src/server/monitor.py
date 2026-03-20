"""File system monitoring module for MCP file monitoring server.

Provides MonitoredEntry and ChangeEvent dataclasses, server-global state
singletons (registry, event buffer, memory object streams, watchdog observer),
and McpFileHandler for bridging watchdog events into the async pipeline.
"""

import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

# --- Configuration from environment ---
EVENT_BUFFER_MAXLEN: int = int(os.environ.get("EVENT_BUFFER_MAXLEN", "1000"))
EVENT_QUEUE_MAXSIZE: int = int(os.environ.get("EVENT_QUEUE_MAXSIZE", "256"))


# --- Dataclasses ---

@dataclass
class MonitoredEntry:
    """A file or directory path registered for monitoring."""

    path: str
    kind: Literal["file", "dir"]
    registered_at: float = field(default_factory=time.time)
    watch: object = field(default=None, repr=False)  # watchdog Watch object


@dataclass
class ChangeEvent:
    """A debounced file system change record, stored in the event buffer."""

    path: str
    event_type: Literal["created", "modified", "deleted", "moved"]
    timestamp: float


# --- Server-global state singletons ---

_registry: dict[str, MonitoredEntry] = {}
_event_buffer: deque[dict] = deque(maxlen=EVENT_BUFFER_MAXLEN)

# MemoryObjectStream pair: watchdog thread → debounce task
_send_stream: MemoryObjectSendStream
_recv_stream: MemoryObjectReceiveStream
_send_stream, _recv_stream = anyio.create_memory_object_stream(
    max_buffer_size=EVENT_QUEUE_MAXSIZE
)

_observer: Observer = Observer()


# --- Watchdog event type mapping ---

_WATCHDOG_EVENT_MAP: dict[type, str] = {
    FileCreatedEvent: "created",
    FileModifiedEvent: "modified",
    FileDeletedEvent: "deleted",
    FileMovedEvent: "moved",
    DirCreatedEvent: "created",
    DirModifiedEvent: "modified",
    DirDeletedEvent: "deleted",
    DirMovedEvent: "moved",
}


# --- Watchdog handler ---

class McpFileHandler(FileSystemEventHandler):
    """Bridge watchdog file system events into the async pipeline via send_nowait."""

    def on_any_event(self, event) -> None:
        event_type = _WATCHDOG_EVENT_MAP.get(type(event))
        if event_type is None:
            return
        raw = {"src_path": event.src_path, "event_type": event_type}
        try:
            _send_stream.send_nowait(raw)
        except anyio.WouldBlock:
            pass  # drop on overflow
