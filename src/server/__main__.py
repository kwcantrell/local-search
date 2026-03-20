import sys

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP("localsearch")


@mcp.tool()
def echo(message: str = Field(..., min_length=1)) -> dict:
    """Echo the input message back with a status field.

    Returns a dict with 'result' (the echoed message) and 'status' ('ok').
    Requires a non-empty message string.
    """
    print(f"echo called with message={message!r}", file=sys.stderr)
    return {"result": message, "status": "ok"}


if __name__ == "__main__":
    mcp.run(transport="stdio")
