"""Integration tests for US1: register_files and list_monitored tools.

All tests use real MCP subprocess via in-process FastMCP session + real file I/O.
No mocks (prohibited by project policy).
"""

import json
import os
import tempfile

from mcp.shared.memory import create_connected_server_and_client_session

from src.server.__main__ import mcp


async def call_tool(client, name, args):
    result = await client.call_tool(name, args)
    if result.isError:
        return None, result
    return json.loads(result.content[0].text), None


# --- register_files tests ---


async def test_register_valid_file():
    """Valid file path is registered and appears in registered list."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_path = os.path.abspath(f.name)
    try:
        async with create_connected_server_and_client_session(mcp) as client:
            data, err = await call_tool(client, "register_files", {"paths": [tmp_path]})
        assert err is None
        assert tmp_path in data["registered"]
        assert data["already_monitored"] == []
        assert data["errors"] == []
    finally:
        os.unlink(tmp_path)


async def test_register_valid_directory():
    """Valid directory path is registered with kind=dir."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = os.path.abspath(tmp_dir)
        async with create_connected_server_and_client_session(mcp) as client:
            data, err = await call_tool(client, "register_files", {"paths": [tmp_dir]})
        assert err is None
        assert tmp_dir in data["registered"]
        assert data["already_monitored"] == []
        assert data["errors"] == []


async def test_register_invalid_path_appears_in_errors():
    """Non-existent path appears in errors, not registered."""
    fake_path = "/nonexistent/path/that/does/not/exist/xyz123"
    async with create_connected_server_and_client_session(mcp) as client:
        data, err = await call_tool(client, "register_files", {"paths": [fake_path]})
    assert err is None
    assert data["registered"] == []
    assert data["already_monitored"] == []
    assert len(data["errors"]) == 1
    assert data["errors"][0]["path"] == os.path.abspath(fake_path)
    assert "reason" in data["errors"][0]


async def test_register_duplicate_path_appears_in_already_monitored():
    """Second registration of same path goes to already_monitored, not registered."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_path = os.path.abspath(f.name)
    try:
        async with create_connected_server_and_client_session(mcp) as client:
            # First registration
            data1, err1 = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert err1 is None
            assert tmp_path in data1["registered"]

            # Second registration (duplicate)
            data2, err2 = await call_tool(
                client, "register_files", {"paths": [tmp_path]}
            )
            assert err2 is None
            assert tmp_path in data2["already_monitored"]
            assert data2["registered"] == []
            assert data2["errors"] == []
    finally:
        os.unlink(tmp_path)


async def test_register_empty_list_returns_invalid_params_error():
    """Empty paths list returns MCP INVALID_PARAMS error."""
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("register_files", {"paths": []})
    assert result.isError


async def test_register_mixed_valid_invalid_paths():
    """Mix of valid and invalid paths: valid in registered, invalid in errors."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        valid_path = os.path.abspath(f.name)
    invalid_path = "/nonexistent/xyz987"
    try:
        async with create_connected_server_and_client_session(mcp) as client:
            data, err = await call_tool(
                client, "register_files", {"paths": [valid_path, invalid_path]}
            )
        assert err is None
        assert valid_path in data["registered"]
        error_paths = [e["path"] for e in data["errors"]]
        assert os.path.abspath(invalid_path) in error_paths
    finally:
        os.unlink(valid_path)


async def test_register_shows_in_list_monitored():
    """After registration, list_monitored shows the registered path."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_path = os.path.abspath(f.name)
    try:
        async with create_connected_server_and_client_session(mcp) as client:
            await call_tool(client, "register_files", {"paths": [tmp_path]})
            data, err = await call_tool(client, "list_monitored", {})
        assert err is None
        monitored_paths = [e["path"] for e in data["monitored"]]
        assert tmp_path in monitored_paths
    finally:
        os.unlink(tmp_path)


# --- list_monitored tests (US4 coverage, same file per tasks.md T019) ---


async def test_list_monitored_empty_when_nothing_registered():
    """list_monitored returns empty list when nothing is registered."""
    async with create_connected_server_and_client_session(mcp) as client:
        data, err = await call_tool(client, "list_monitored", {})
    assert err is None
    assert data["monitored"] == []


async def test_list_monitored_returns_all_registered_paths():
    """list_monitored returns all registered paths after multiple registrations."""
    with tempfile.NamedTemporaryFile(delete=False) as f1:
        path1 = os.path.abspath(f1.name)
    with tempfile.NamedTemporaryFile(delete=False) as f2:
        path2 = os.path.abspath(f2.name)
    try:
        async with create_connected_server_and_client_session(mcp) as client:
            await call_tool(client, "register_files", {"paths": [path1, path2]})
            data, err = await call_tool(client, "list_monitored", {})
        assert err is None
        monitored_paths = [e["path"] for e in data["monitored"]]
        assert path1 in monitored_paths
        assert path2 in monitored_paths
    finally:
        os.unlink(path1)
        os.unlink(path2)


async def test_list_monitored_file_kind():
    """list_monitored returns kind='file' for files."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp_path = os.path.abspath(f.name)
    try:
        async with create_connected_server_and_client_session(mcp) as client:
            await call_tool(client, "register_files", {"paths": [tmp_path]})
            data, err = await call_tool(client, "list_monitored", {})
        assert err is None
        entry = next(e for e in data["monitored"] if e["path"] == tmp_path)
        assert entry["kind"] == "file"
        assert "registered_at" in entry
    finally:
        os.unlink(tmp_path)


async def test_list_monitored_dir_kind():
    """list_monitored returns kind='dir' for directories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = os.path.abspath(tmp_dir)
        async with create_connected_server_and_client_session(mcp) as client:
            await call_tool(client, "register_files", {"paths": [tmp_dir]})
            data, err = await call_tool(client, "list_monitored", {})
        assert err is None
        entry = next(e for e in data["monitored"] if e["path"] == tmp_dir)
        assert entry["kind"] == "dir"
