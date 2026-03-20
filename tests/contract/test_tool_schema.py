"""Contract tests: validate tool schemas match contracts/tool-schema.json."""

import json
from pathlib import Path

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from src.server.__main__ import mcp

SCHEMA_PATH = (
    Path(__file__).parents[2]
    / "specs"
    / "001-agent-mcp-mvp"
    / "contracts"
    / "tool-schema.json"
)


@pytest.fixture(scope="module")
def contract_schema():
    return json.loads(SCHEMA_PATH.read_text())


async def test_echo_tool_input_has_message_field(contract_schema):
    """ToolInput contract: echo requires a non-empty 'message' string."""
    tool_input = contract_schema["definitions"]["ToolInput"]
    assert "message" in tool_input["properties"]
    msg_schema = tool_input["properties"]["message"]
    assert msg_schema["type"] == "string"
    assert msg_schema["minLength"] == 1
    assert "message" in tool_input["required"]


async def test_echo_tool_result_schema(contract_schema):
    """ToolResult contract: success response has 'result' and 'status' fields."""
    tool_result = contract_schema["definitions"]["ToolResult"]
    assert "result" in tool_result["properties"]
    assert "status" in tool_result["properties"]
    assert tool_result["properties"]["status"]["enum"] == ["ok"]
    assert "result" in tool_result["required"]
    assert "status" in tool_result["required"]


async def test_echo_tool_error_schema(contract_schema):
    """ToolError contract: error response has 'code' and 'message' fields."""
    tool_error = contract_schema["definitions"]["ToolError"]
    assert "code" in tool_error["properties"]
    assert "message" in tool_error["properties"]
    assert tool_error["properties"]["code"]["type"] == "integer"
    assert "code" in tool_error["required"]
    assert "message" in tool_error["required"]


async def test_echo_tool_actual_output_matches_result_schema():
    """Echo tool output at runtime must conform to ToolResult contract."""
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("echo", {"message": "contract-check"})
    assert not result.isError
    parsed = json.loads(result.content[0].text)
    assert isinstance(parsed["result"], str)
    assert parsed["status"] == "ok"
    # No extra fields (additionalProperties: false)
    assert set(parsed.keys()) == {"result", "status"}


async def test_echo_tool_input_schema_via_fastmcp():
    """FastMCP-generated schema for echo must require non-empty message."""
    async with create_connected_server_and_client_session(mcp) as client:
        tools_result = await client.list_tools()
    echo_tool = next((t for t in tools_result.tools if t.name == "echo"), None)
    assert echo_tool is not None, "echo tool must be registered"
    input_schema = echo_tool.inputSchema
    assert "message" in input_schema.get("properties", {})
    assert input_schema.get("required") is not None
    assert "message" in input_schema["required"]


# --- US1: register_files and list_monitored contract schema tests ---


async def _get_tools():
    async with create_connected_server_and_client_session(mcp) as client:
        tools_result = await client.list_tools()
    return {t.name: t for t in tools_result.tools}


async def test_register_files_tool_registered():
    """register_files tool must be registered in FastMCP."""
    tools = await _get_tools()
    assert "register_files" in tools, "register_files tool must be registered"


async def test_register_files_input_schema():
    """register_files must accept paths: list[str] as required parameter."""
    tools = await _get_tools()
    schema = tools["register_files"].inputSchema
    props = schema.get("properties", {})
    assert "paths" in props, "register_files must have 'paths' parameter"
    paths_schema = props["paths"]
    assert paths_schema["type"] == "array", "paths must be type array"
    assert paths_schema["items"]["type"] == "string", "paths items must be type string"
    assert "paths" in schema.get("required", []), "paths must be required"


async def test_register_files_response_keys():
    """register_files must return registered, already_monitored, and errors keys."""
    import tempfile, os

    async with create_connected_server_and_client_session(mcp) as client:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name
        try:
            result = await client.call_tool("register_files", {"paths": [tmp_path]})
            assert not result.isError
            parsed = json.loads(result.content[0].text)
            assert "registered" in parsed, "response must have 'registered' key"
            assert "already_monitored" in parsed, "response must have 'already_monitored' key"
            assert "errors" in parsed, "response must have 'errors' key"
        finally:
            os.unlink(tmp_path)


async def test_list_monitored_tool_registered():
    """list_monitored tool must be registered in FastMCP."""
    tools = await _get_tools()
    assert "list_monitored" in tools, "list_monitored tool must be registered"


async def test_list_monitored_input_schema():
    """list_monitored must accept no required parameters."""
    tools = await _get_tools()
    schema = tools["list_monitored"].inputSchema
    required = schema.get("required", [])
    assert required == [], "list_monitored must have no required parameters"


async def test_list_monitored_response_keys():
    """list_monitored must return monitored key with a list."""
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("list_monitored", {})
    assert not result.isError
    parsed = json.loads(result.content[0].text)
    assert "monitored" in parsed, "response must have 'monitored' key"
    assert isinstance(parsed["monitored"], list), "monitored must be a list"
