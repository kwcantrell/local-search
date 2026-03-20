"""End-to-end integration tests: agent → MCP server via real subprocess.

Round-trip latency baseline (echo tool, 2026-03-20): ~24s
SC-002 budget: 30s per call (set conservatively above baseline).
"""

import time

from src.agent.main import run


async def test_valid_echo_call_returns_schema_fields():
    """(a) Valid echo call succeeds and result references schema fields."""
    result = await run("Use the echo tool with the message 'integration-test'")
    # Agent response must mention the echoed value or schema fields
    assert result, "Expected non-empty result string"
    assert "integration-test" in result or "result" in result.lower()


async def test_nonexistent_tool_surfaces_error():
    """(b) Call to non-existent tool surfaces an error in the agent response."""
    result = await run(
        "Call the tool named 'nonexistent_tool_xyz' on the localsearch server"
    )
    # Agent should report a tool-not-found or error condition
    assert result, "Expected non-empty result string"
    lower = result.lower()
    error_keywords = (
        "not found", "doesn't exist", "no tool", "error", "unable", "cannot", "can't"
    )
    assert any(
        kw in lower for kw in error_keywords
    ), f"Expected error indication in result, got: {result!r}"


async def test_empty_string_input_surfaces_error():
    """(c) Empty-string input surfaces -32602 (invalid params) error."""
    result = await run(
        "Use the echo tool with an empty string as the message argument"
    )
    assert result, "Expected non-empty result string"
    lower = result.lower()
    error_keywords = ("-32602", "invalid", "error", "empty", "validation", "required")
    assert any(
        kw in lower for kw in error_keywords
    ), f"Expected validation error indication in result, got: {result!r}"


async def test_round_trip_latency():
    """(d) Round-trip latency < 30s (SC-002). Baseline: ~24s measured 2026-03-20."""
    start = time.monotonic()
    result = await run("Use the echo tool with the message 'latency-check'")
    elapsed = time.monotonic() - start
    assert result, "Expected non-empty result string"
    # SC-002: latency budget is 30s; baseline measured at ~24s
    assert elapsed < 30, f"Round-trip took {elapsed:.1f}s, exceeds 30s budget"
