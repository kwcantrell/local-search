import json

from mcp.shared.memory import create_connected_server_and_client_session

from src.server.__main__ import mcp


async def test_echo_returns_all_required_fields():
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("echo", {"message": "hello world"})
    assert not result.isError
    assert len(result.content) == 1
    parsed = json.loads(result.content[0].text)
    assert parsed["result"] == "hello world"
    assert parsed["status"] == "ok"


async def test_echo_returns_result_and_status_fields():
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("echo", {"message": "test"})
    parsed = json.loads(result.content[0].text)
    assert "result" in parsed
    assert "status" in parsed


async def test_echo_empty_message_returns_error():
    """FastMCP must reject empty message (minLength: 1 via Pydantic Field)."""
    async with create_connected_server_and_client_session(mcp) as client:
        result = await client.call_tool("echo", {"message": ""})
    assert result.isError is True


async def test_echo_sequential_calls_map_to_inputs():
    """FR-005: each result correctly maps to its input (sequential guarantee)."""
    async with create_connected_server_and_client_session(mcp) as client:
        result1 = await client.call_tool("echo", {"message": "first"})
        result2 = await client.call_tool("echo", {"message": "second"})
    parsed1 = json.loads(result1.content[0].text)
    parsed2 = json.loads(result2.content[0].text)
    assert parsed1["result"] == "first"
    assert parsed2["result"] == "second"
    assert parsed1["result"] != parsed2["result"]
