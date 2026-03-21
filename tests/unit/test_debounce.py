"""Unit tests for debounce pipeline logic.

Tests the debounce_task() coroutine directly using real anyio MemoryObjectStream
pairs and asyncio. No mocks — real async primitives only.

SC-004: Multiple rapid events for the same path within the debounce window must
produce exactly one ChangeEvent in _event_buffer (last-write-wins coalescing).
"""


import anyio
import pytest

import src.server.monitor as monitor_module
from src.server.monitor import MonitoredEntry


def _make_streams(max_buffer_size: int = 256):
    """Create a fresh MemoryObjectStream pair for testing."""
    return anyio.create_memory_object_stream(max_buffer_size=max_buffer_size)


def _raw(path: str, event_type: str) -> dict:
    return {"src_path": path, "event_type": event_type}


async def _run_debounce_for(send_stream, seconds: float) -> None:
    """Run the debounce task for `seconds` then cancel it."""
    from src.server.debounce import debounce_task

    with anyio.move_on_after(seconds):
        await debounce_task()


@pytest.fixture(autouse=True)
def reset_monitor_state(tmp_path):
    """Reset server-global state before each test."""
    orig_registry = monitor_module._registry.copy()
    orig_buffer = monitor_module._event_buffer.copy()
    orig_send = monitor_module._send_stream
    orig_recv = monitor_module._recv_stream

    # Fresh streams and state for isolation
    send, recv = _make_streams()
    monitor_module._send_stream = send
    monitor_module._recv_stream = recv
    monitor_module._registry.clear()
    monitor_module._event_buffer.clear()

    yield tmp_path

    # Restore
    monitor_module._send_stream = orig_send
    monitor_module._recv_stream = orig_recv
    monitor_module._registry.clear()
    monitor_module._registry.update(orig_registry)
    monitor_module._event_buffer.clear()
    monitor_module._event_buffer.extend(orig_buffer)


async def test_rapid_events_coalesced_to_one(reset_monitor_state):
    """SC-004: N rapid events for the same path within the window → 1 ChangeEvent."""
    tmp_path = reset_monitor_state
    file_path = str(tmp_path / "watched.txt")

    # Register the path so the debounce filter lets it through
    monitor_module._registry[file_path] = MonitoredEntry(
        path=file_path, kind="file"
    )

    # Send 50 rapid events — all within the debounce window
    for _ in range(50):
        monitor_module._send_stream.send_nowait(_raw(file_path, "modified"))

    # Close send side so debounce_task's receive() raises EndOfStream after draining
    await monitor_module._send_stream.aclose()

    from src.server.debounce import debounce_task

    with anyio.move_on_after(3.0):
        await debounce_task()

    assert len(monitor_module._event_buffer) == 1
    event = monitor_module._event_buffer[0]
    assert event["path"] == file_path
    assert event["event_type"] == "modified"


async def test_last_write_wins_coalescing(reset_monitor_state):
    """modified → deleted sequence → event_type is 'deleted' (last-write-wins)."""
    tmp_path = reset_monitor_state
    file_path = str(tmp_path / "watched.txt")

    monitor_module._registry[file_path] = MonitoredEntry(
        path=file_path, kind="file"
    )

    # Send: modified first, then deleted
    monitor_module._send_stream.send_nowait(_raw(file_path, "modified"))
    monitor_module._send_stream.send_nowait(_raw(file_path, "modified"))
    monitor_module._send_stream.send_nowait(_raw(file_path, "deleted"))

    await monitor_module._send_stream.aclose()

    from src.server.debounce import debounce_task

    with anyio.move_on_after(3.0):
        await debounce_task()

    assert len(monitor_module._event_buffer) == 1
    assert monitor_module._event_buffer[0]["event_type"] == "deleted"


async def test_unregistered_paths_filtered_out(reset_monitor_state):
    """Events for paths not in _registry must not appear in _event_buffer."""
    tmp_path = reset_monitor_state
    unregistered_path = str(tmp_path / "not_watched.txt")

    # _registry is empty — no paths registered
    monitor_module._send_stream.send_nowait(_raw(unregistered_path, "modified"))

    await monitor_module._send_stream.aclose()

    from src.server.debounce import debounce_task

    with anyio.move_on_after(3.0):
        await debounce_task()

    assert len(monitor_module._event_buffer) == 0


async def test_no_spurious_flushes_when_idle(reset_monitor_state):
    """Idle debounce task with no events must not write anything to _event_buffer."""
    # Do NOT send any events — just let the task run briefly then cancel
    from src.server.debounce import debounce_task

    with anyio.move_on_after(0.3):
        await debounce_task()

    assert len(monitor_module._event_buffer) == 0


async def test_events_for_registered_dir_path_pass_through(reset_monitor_state):
    """Events for files inside a registered directory must appear in _event_buffer."""
    tmp_path = reset_monitor_state
    dir_path = str(tmp_path)
    file_inside = str(tmp_path / "inside.txt")

    # Register the directory, not the file directly
    monitor_module._registry[dir_path] = MonitoredEntry(
        path=dir_path, kind="dir"
    )

    monitor_module._send_stream.send_nowait(_raw(file_inside, "created"))

    await monitor_module._send_stream.aclose()

    from src.server.debounce import debounce_task

    with anyio.move_on_after(3.0):
        await debounce_task()

    assert len(monitor_module._event_buffer) == 1
    assert monitor_module._event_buffer[0]["path"] == file_inside
    assert monitor_module._event_buffer[0]["event_type"] == "created"


async def test_multiple_paths_each_get_one_event(reset_monitor_state):
    """Rapid events for two different paths each produce exactly one coalesced event."""
    tmp_path = reset_monitor_state
    path_a = str(tmp_path / "a.txt")
    path_b = str(tmp_path / "b.txt")

    monitor_module._registry[path_a] = MonitoredEntry(path=path_a, kind="file")
    monitor_module._registry[path_b] = MonitoredEntry(path=path_b, kind="file")

    for _ in range(10):
        monitor_module._send_stream.send_nowait(_raw(path_a, "modified"))
    for _ in range(10):
        monitor_module._send_stream.send_nowait(_raw(path_b, "deleted"))

    await monitor_module._send_stream.aclose()

    from src.server.debounce import debounce_task

    with anyio.move_on_after(3.0):
        await debounce_task()

    assert len(monitor_module._event_buffer) == 2
    events_by_path = {e["path"]: e["event_type"] for e in monitor_module._event_buffer}
    assert events_by_path[path_a] == "modified"
    assert events_by_path[path_b] == "deleted"
