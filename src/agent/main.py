from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query


async def run(prompt: str) -> str:
    options = ClaudeAgentOptions(
        mcp_servers={
            "localsearch": {
                "command": "python",
                "args": ["-m", "src.server"],
            }
        },
        allowed_tools=["mcp__localsearch__*"],
    )
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, SystemMessage) and msg.subtype == "init":
            failed = [
                s
                for s in msg.data.get("mcp_servers", [])
                if s.get("status") != "connected"
            ]
            if failed:
                raise RuntimeError(f"MCP servers failed to connect: {failed}")
        if isinstance(msg, ResultMessage) and msg.subtype == "success":
            return msg.result
    raise RuntimeError("No result received from agent")
