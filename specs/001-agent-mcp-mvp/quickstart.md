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
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0"}}}' | python -m src.server
```

You should see an MCP `initialize` response on stdout within 1 second. Press Ctrl-C to stop.

## 3. Run the agent

```bash
export ANTHROPIC_API_KEY=<your key>
python -m src.agent "Use the echo tool to echo the message 'hello world' and tell me the result."
```

Expected output (approximately):

```
The echo tool returned: result='hello world', status='ok'
```

## 4. Run the tests

```bash
uv run pytest
```

All three test suites run:
- **Unit** (`tests/unit/`) — in-memory FastMCP client, no subprocess
- **Contract** (`tests/contract/`) — tool schema validation
- **Integration** (`tests/integration/`) — full subprocess end-to-end

Expected: all tests pass, round-trip latency printed for the integration test.

## 5. Trigger error paths (optional)

Call a non-existent tool:
```bash
python -m src.agent "Call the tool called 'nonexistent' on the localsearch MCP server."
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
