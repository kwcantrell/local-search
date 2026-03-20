# Quickstart: Agent MCP Server MVP

Get the agent calling the MCP server in under 10 minutes.

## Prerequisites

- Python 3.11+
- `uv` package manager (`pip install uv` or see [uv docs](https://docs.astral.sh/uv/))
- A valid `ANTHROPIC_API_KEY` environment variable

## 1. Install dependencies

```bash
uv sync
```

This installs `mcp`, `claude-agent-sdk`, `pytest`, and `pytest-asyncio` from `pyproject.toml`.

## 2. Verify the MCP server starts

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' | uv run python -m src.server
```

You should see an MCP `initialize` response (JSON with `"serverInfo":{"name":"localsearch",...}`) on stdout within 1 second.

## 3. Run the agent

```bash
export ANTHROPIC_API_KEY=<your key>
uv run python -m src.agent "Use the echo tool to echo the message 'hello world' and tell me the result."
```

Expected output (approximately):

```
Tool called: mcp__localsearch__echo
Result: The echo tool returned the message 'hello world' with status 'ok'.
```

## 4. Run the tests

```bash
uv run pytest
```

All three test suites run:
- **Unit** (`tests/unit/`) — real subprocess MCP client, tool behaviour tests
- **Contract** (`tests/contract/`) — tool schema validation via real subprocess
- **Integration** (`tests/integration/`) — full agent end-to-end via subprocess

Expected: all tests pass, round-trip latency printed for the integration test.

## 5. Trigger error paths (optional)

Call a non-existent tool:
```bash
uv run python -m src.agent "Call the tool called 'nonexistent' on the localsearch MCP server."
```

Expected: agent surfaces a clear error message — no hang, no crash.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `CLINotFoundError` | Ensure `claude-agent-sdk` is installed (`uv sync`) |
| `CLIConnectionError` | Check the server starts correctly (step 2 above) |
| MCP server fails to connect | Check `ANTHROPIC_API_KEY` is set; check subprocess output |
| `stdout` garbage in MCP stream | Ensure no `print()` calls in `src/server/` — use `sys.stderr` |
