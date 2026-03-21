"""Integration tests for US2: poll_events tool — file change notifications.

All tests use real MCP in-process FastMCP session + real file I/O.
No mocks (prohibited by project policy).
"""

import asyncio
import json
import os
import tempfile
import time

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from src.server.__main__ import mcp


async def call_tool(client, name, args):
    result = await client.call_tool(name, args)
    if result.isError:
        return None, result
    return json.loads(result.content[0].text), None


async def test_poll_events_empty_when_no_changes():
    """poll_events returns empty events list when no file changes have occurred."""
    async with create_connected_server_and_client_session(mcp) as client:
        data, err = await call_tool(client, "poll_events", {"since_ts": 0.0})
    assert err is None
    assert data["events"] == []
    assert data["count"] == 0


async def test_poll_events_always_returns_both_keys():
    """poll_events always returns events and count keys even when empty."""
    async with create_connected_server_and_client_session(mcp) as client:
        data, err = await call_tool(client, "poll_events", {"since_ts": 0.0})
    assert err is None
    assert "events" in data
    assert "count" in data


async def test_file_modify_produces_notification():
    """File modification triggers a notification visible via poll_events within 2s (SC-002)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        tmp_path = os.path.abspath(f.name)
        f.write(b"initial content")

    try:
        async with create_connected_server_and_client_session(mcp) as client:
            # Register the file
            reg_data, reg_err = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert reg_err is None
            assert tmp_path in reg_data["registered"]

            before_ts = time.time()

            # Trigger a file modification
            with open(tmp_path, "w") as f:
                f.write("modified content")

            # Poll until we see the event (up to 2 seconds, SC-002)
            deadline = time.time() + 2.0
            found_event = None
            while time.time() < deadline:
                await asyncio.sleep(0.1)
                poll_data, poll_err = await call_tool(
                    client, "poll_events", {"since_ts": before_ts}
                )
                assert poll_err is None
                matching = [
                    e for e in poll_data["events"] if e["path"] == tmp_path
                ]
                if matching:
                    found_event = matching[0]
                    break

        assert found_event is not None, "Expected a notification for the modified file within 2s"
        assert found_event["event_type"] in ("modified", "created", "deleted", "moved")
        assert found_event["timestamp"] > before_ts
    finally:
        os.unlink(tmp_path)


async def test_file_delete_produces_deletion_event():
    """File deletion triggers a deleted event visible via poll_events."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        tmp_path = os.path.abspath(f.name)
        f.write(b"content to delete")

    try:
        async with create_connected_server_and_client_session(mcp) as client:
            reg_data, reg_err = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert reg_err is None

            before_ts = time.time()

            # Delete the file
            os.unlink(tmp_path)

            # Poll for deletion event (up to 2 seconds)
            deadline = time.time() + 2.0
            found_event = None
            while time.time() < deadline:
                await asyncio.sleep(0.1)
                poll_data, poll_err = await call_tool(
                    client, "poll_events", {"since_ts": before_ts}
                )
                assert poll_err is None
                matching = [
                    e for e in poll_data["events"] if e["path"] == tmp_path
                ]
                if matching:
                    found_event = matching[0]
                    break

        assert found_event is not None, "Expected a deletion event within 2s"
        assert found_event["event_type"] == "deleted"
    except Exception:
        # File may already be deleted
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


async def test_rapid_writes_coalesced_to_one_event():
    """50 rapid writes within debounce window produce exactly 1 coalesced event (SC-004)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        tmp_path = os.path.abspath(f.name)

    try:
        async with create_connected_server_and_client_session(mcp) as client:
            reg_data, reg_err = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert reg_err is None

            before_ts = time.time()

            # Write 50 times rapidly (well within 0.5s debounce window)
            for i in range(50):
                with open(tmp_path, "w") as f:
                    f.write(f"write {i}")

            # Wait for debounce window to close (0.5s) + some margin
            await asyncio.sleep(1.0)

            poll_data, poll_err = await call_tool(
                client, "poll_events", {"since_ts": before_ts}
            )
            assert poll_err is None

        matching = [e for e in poll_data["events"] if e["path"] == tmp_path]
        assert len(matching) == 1, (
            f"Expected exactly 1 coalesced event for 50 rapid writes, got {len(matching)}"
        )
    finally:
        os.unlink(tmp_path)


async def test_poll_events_no_duplicate_events():
    """poll_events(since_ts=last_ts) returns no duplicate events on repeated calls."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        tmp_path = os.path.abspath(f.name)

    try:
        async with create_connected_server_and_client_session(mcp) as client:
            reg_data, reg_err = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert reg_err is None

            before_ts = time.time()

            # Trigger one modification
            with open(tmp_path, "w") as f:
                f.write("first write")

            # Wait for debounce window + margin
            await asyncio.sleep(1.0)

            # First poll — should see the event
            poll1_data, poll1_err = await call_tool(
                client, "poll_events", {"since_ts": before_ts}
            )
            assert poll1_err is None
            assert poll1_data["count"] >= 1

            # Update last_ts to max timestamp seen
            last_ts = max(e["timestamp"] for e in poll1_data["events"])

            # Second poll with updated since_ts — should see no new events
            poll2_data, poll2_err = await call_tool(
                client, "poll_events", {"since_ts": last_ts}
            )
            assert poll2_err is None

        # No events with timestamp > last_ts should appear
        new_events = [
            e for e in poll2_data["events"] if e["path"] == tmp_path
        ]
        assert new_events == [], f"Expected no duplicates, got {new_events}"
    finally:
        os.unlink(tmp_path)


async def test_poll_events_sorted_ascending_by_timestamp():
    """poll_events returns events sorted in ascending timestamp order."""
    async with create_connected_server_and_client_session(mcp) as client:
        # Artificially populate buffer via module state access and poll
        import src.server.monitor as _monitor

        _monitor._event_buffer.append(
            {"path": "/tmp/a", "event_type": "modified", "timestamp": 100.0}
        )
        _monitor._event_buffer.append(
            {"path": "/tmp/b", "event_type": "created", "timestamp": 50.0}
        )
        _monitor._event_buffer.append(
            {"path": "/tmp/c", "event_type": "deleted", "timestamp": 200.0}
        )

        poll_data, poll_err = await call_tool(client, "poll_events", {"since_ts": 0.0})

    assert poll_err is None
    timestamps = [e["timestamp"] for e in poll_data["events"]]
    assert timestamps == sorted(timestamps), "Events must be sorted by ascending timestamp"
