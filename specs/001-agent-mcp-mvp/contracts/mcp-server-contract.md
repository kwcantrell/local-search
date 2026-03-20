# MCP Server Contract: localsearch

**Server name**: `localsearch`
**Transport**: stdio (JSON-RPC 2.0 over stdin/stdout)
**Version**: 0.1.0 (MVP)

---

## Overview

The `localsearch` MCP server exposes tools that a Claude agent can invoke via stdio transport. The agent launches the server as a subprocess (`python -m src.server`) and communicates using the Model Context Protocol.

---

## Tools

### `echo`

**Fully-qualified name** (agent-side): `mcp__localsearch__echo`
**Description**: Echo the input message back with a status field. Returns `{result, status}`.

#### Input

```json
{
  "message": "<string, minLength: 1>"
}
```

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `message` | `string` | ✅ | Non-empty |

#### Success Output

Content block type: `text`. The `text` field is a JSON-encoded object:

```json
{
  "result": "<echoed message>",
  "status": "ok"
}
```

| Field | Type | Always present |
|-------|------|----------------|
| `result` | `string` | ✅ |
| `status` | `"ok"` | ✅ |

#### Error Output

When `message` is empty or missing:

```json
{
  "code": -32602,
  "message": "Invalid params: message must be non-empty"
}
```

`is_error` is `true` on the MCP content envelope.

---

## Protocol Invariants

1. **stdout is the protocol stream** — the server MUST NOT write anything to stdout except MCP JSON-RPC messages. All logging goes to stderr.
2. **Errors are structured** — the server MUST return MCP error responses for all failure modes. Stack traces MUST NOT appear in production responses (constitution requirement).
3. **No blocking I/O on the event loop** — all file or network operations within tool handlers MUST be async (constitution Principle III).
4. **Tool descriptions ≤3 sentences** — concise, informative, no marketing language (constitution Principle IV).

---

## Connection Lifecycle

```
Agent                              MCP Server (subprocess)
  │                                       │
  │── python -m src.server ──────────────▶│  (spawn subprocess)
  │                                       │  initialize FastMCP
  │◀── MCP initialize response ──────────│
  │── tools/list ─────────────────────────▶│
  │◀── [echo, ...] ───────────────────────│
  │                                       │
  │── tools/call {name:"echo", args:{}} ──▶│
  │◀── {content:[{type:"text", text:…}]} ─│
  │                                       │
  │── (session end) ──────────────────────▶│  (process terminated)
```

---

## Error Code Reference

| Code | Name | Trigger |
|------|------|---------|
| `-32602` | Invalid params | Missing required param or failed schema validation |
| `-32601` | Method not found | Tool name does not exist on this server |
| `-32000` | Server error | Unhandled exception during tool execution |
