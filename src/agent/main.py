import asyncio

from claude_agent_sdk import (
    ClaudeAgentOptions,
    CLIConnectionError,
    ProcessError,
    ResultMessage,
    SystemMessage,
    query,
)

_DEFAULT_TIMEOUT = 60


async def run(prompt: str, timeout: float = _DEFAULT_TIMEOUT) -> str:
    options = ClaudeAgentOptions(
        mcp_servers={
            "localsearch": {
                "command": "python",
                "args": ["-m", "src.server"],
            }
        },
        allowed_tools=["mcp__localsearch__*"],
    )
    try:
        result = await asyncio.wait_for(_run_query(prompt, options), timeout=timeout)
    except CLIConnectionError as e:
        raise RuntimeError(f"Could not connect to Claude Code CLI: {e}") from e
    except ProcessError as e:
        raise RuntimeError(f"Claude Code process failed: {e}") from e
    except asyncio.TimeoutError as e:
        raise RuntimeError(
            f"Agent did not complete within {timeout}s timeout"
        ) from e
    return result


async def _run_query(prompt: str, options: ClaudeAgentOptions) -> str:
    configured = set(options.mcp_servers or {})
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, SystemMessage) and msg.subtype == "init":
            failed = [
                s
                for s in msg.data.get("mcp_servers", [])
                if s.get("name") in configured and s.get("status") != "connected"
            ]
            if failed:
                raise RuntimeError(f"MCP servers failed to connect: {failed}")
        if isinstance(msg, ResultMessage) and msg.subtype == "success":
            return msg.result
    raise RuntimeError("No result received from agent")
