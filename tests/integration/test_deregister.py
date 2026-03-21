"""Integration tests for US3: deregister_files tool.

All tests use real MCP in-process FastMCP session + real file I/O.
No mocks (prohibited by project policy).
"""

import json
import os
import tempfile

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from src.server.__main__ import mcp


async def call_tool(client, name, args):
    result = await client.call_tool(name, args)
    if result.isError:
        return None, result
    return json.loads(result.content[0].text), None


async def test_deregister_stops_notifications():
    """After deregistering a file, writes to it produce no events in poll_events."""
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

            # Deregister the file
            dereg_data, dereg_err = await call_tool(
                client, "deregister_files", {"paths": [tmp_path]}
            )
            assert dereg_err is None
            assert tmp_path in dereg_data["deregistered"]
            assert dereg_data["not_monitored"] == []

            # Trigger a file write after deregistration
            with open(tmp_path, "w") as f:
                f.write("modified after deregister")

            # Wait longer than the debounce window (0.5s) plus margin
            await anyio.sleep(0.6)

            poll_data, poll_err = await call_tool(
                client, "poll_events", {"since_ts": 0.0}
            )
            assert poll_err is None

        # No events for the deregistered file should appear
        matching = [e for e in poll_data["events"] if e["path"] == tmp_path]
        assert len(matching) == 0, (
            f"Expected 0 events for deregistered file, got {len(matching)}: {matching}"
        )
    finally:
        os.unlink(tmp_path)


async def test_deregister_unknown_path_returns_not_monitored():
    """Deregistering a path that was never registered returns it in not_monitored, no error."""
    never_registered = os.path.abspath("/tmp/never_registered_xyz_12345.txt")

    async with create_connected_server_and_client_session(mcp) as client:
        dereg_data, dereg_err = await call_tool(
            client, "deregister_files", {"paths": [never_registered]}
        )

    assert dereg_err is None
    assert never_registered in dereg_data["not_monitored"]
    assert dereg_data["deregistered"] == []


async def test_deregister_then_reregister_works():
    """A file can be deregistered and then re-registered; it appears in list_monitored."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        tmp_path = os.path.abspath(f.name)
        f.write(b"content")

    try:
        async with create_connected_server_and_client_session(mcp) as client:
            # Register
            reg_data, reg_err = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert reg_err is None
            assert tmp_path in reg_data["registered"]

            # Deregister
            dereg_data, dereg_err = await call_tool(
                client, "deregister_files", {"paths": [tmp_path]}
            )
            assert dereg_err is None
            assert tmp_path in dereg_data["deregistered"]

            # Re-register
            rereg_data, rereg_err = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert rereg_err is None
            assert tmp_path in rereg_data["registered"]

            # Confirm it appears in list_monitored
            list_data, list_err = await call_tool(client, "list_monitored", {})
            assert list_err is None

        monitored_paths = [e["path"] for e in list_data["monitored"]]
        assert tmp_path in monitored_paths
    finally:
        os.unlink(tmp_path)


async def test_deregister_empty_list_returns_invalid_params():
    """Calling deregister_files with an empty list returns an MCP error (isError=True)."""
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("deregister_files", {"paths": []})

    assert result.isError
