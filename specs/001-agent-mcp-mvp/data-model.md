# Data Model: Agent MCP Server MVP

**Branch**: `001-agent-mcp-mvp` | **Date**: 2026-03-20

## Entities

### Agent

The autonomous entity that sends tool call requests and processes results.

| Field | Type | Description |
|-------|------|-------------|
| `prompt` | `str` | Natural language input (from human or tasks.md entry) |
| `mcp_servers` | `dict[str, MCPServerConfig]` | Named map of MCP servers the agent may connect to |
| `allowed_tools` | `list[str]` | Allowlist of tool identifiers (e.g., `mcp__localsearch__*`) |

**Behaviour**: Stateless per invocation. Each call to `query()` starts a fresh agent session.

---

### MCPServerConfig

Configuration for a single MCP server launched as a subprocess.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | `str` | ✅ | Executable to launch (e.g., `"python"`) |
| `args` | `list[str]` | ✅ | Arguments (e.g., `["-m", "src.server"]`) |
| `env` | `dict[str, str]` | ❌ | Additional environment variables for the subprocess |

**Constraints**: `command` + `args` must produce a process that speaks MCP stdio JSON-RPC on stdin/stdout.

---

### MCP Server

The service that exposes tools over stdio.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Server identifier used in tool routing (e.g., `"localsearch"`) |
| `tools` | `list[Tool]` | Registered tool definitions |

**Lifecycle**: Launched as subprocess by agent; terminated when agent session ends.

---

### Tool

A named, callable capability exposed by the MCP server.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Unique tool identifier within the server (snake_case) |
| `description` | `str` | ≤3 sentences; self-documenting; no marketing language (Principle IV) |
| `input_schema` | `JSONSchema` | Auto-generated from Python type annotations |
| `output_schema` | `JSONSchema` | Auto-generated from return type annotation |

**Validation**: FastMCP validates all inputs against `input_schema` before invoking the handler. Invalid inputs produce a structured MCP error — never a Python exception surfaced raw.

---

### ToolCall

A request made by the agent to invoke a specific tool.

| Field | Type | Description |
|-------|------|-------------|
| `tool_name` | `str` | Fully-qualified: `mcp__{server}__{tool}` (agent-side) or bare `{tool}` (server-side) |
| `arguments` | `dict[str, Any]` | Input parameters matching the tool's `input_schema` |

---

### ToolResult

The structured response returned by the MCP server after executing a tool call.

| Field | Type | Description |
|-------|------|-------------|
| `content` | `list[ContentBlock]` | One or more content blocks (see below) |
| `is_error` | `bool` | `true` if the tool call failed; `false` on success |

**ContentBlock** (text type — used for JSON-serialized dict results):

| Field | Type | Description |
|-------|------|-------------|
| `type` | `"text"` | Always `"text"` for structured dict returns |
| `text` | `str` | JSON-encoded dict with named fields the agent can reference by key |

**Invariant**: On success, `text` is a valid JSON object with at least one named field. On error, `is_error` is `true` and `text` contains a human-readable error description.

---

### ToolError

Returned in place of a ToolResult when a tool call fails.

| Field | Type | Description |
|-------|------|-------------|
| `code` | `int` | MCP JSON-RPC error code |
| `message` | `str` | Human-readable error description |
| `data` | `Any` | Optional structured context (e.g., validation details) |

**Error codes used**:
| Code | Meaning |
|------|---------|
| `-32602` | Invalid params (malformed/missing input) |
| `-32601` | Method not found (tool does not exist) |
| `-32000` | Server error (tool execution failure) |

---

## State Transitions

```
Agent session lifecycle:

  INIT
    │  query() called with prompt + options
    ▼
  CONNECTING
    │  MCP server subprocess launched
    │  SystemMessage(subtype="init") received
    ▼
  READY  ──── connection failed ──▶  ERROR (CLIConnectionError)
    │
    │  Agent receives prompt, decides to call tool
    ▼
  TOOL_CALLING
    │  ToolCall dispatched to MCP server
    ▼
  AWAITING_RESULT
    │
    ├── success ──▶  TOOL_CALLED  (ToolResult.is_error=false)
    │                    │
    │                    │  Agent uses result, may call more tools
    │                    └──▶  TOOL_CALLING  (loop) or  DONE
    │
    └── failure ──▶  TOOL_ERROR   (ToolResult.is_error=true)
                         │
                         │  Agent surfaces error; no silent hang
                         └──▶  DONE (with error in ResultMessage)
```

---

## MVP Demo Tool: `echo`

For validation of the full integration loop, the MVP ships one demo tool:

| Attribute | Value |
|-----------|-------|
| Name | `echo` |
| Server | `localsearch` |
| Fully-qualified | `mcp__localsearch__echo` |
| Description | `Echo the input message back with a status field. Returns {result, status}.` |
| Input | `message: str` — the string to echo |
| Output | `{"result": <message>, "status": "ok"}` |
| Error case | Empty string → MCP error `-32602` (invalid params) |
