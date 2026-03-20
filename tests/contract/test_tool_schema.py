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
