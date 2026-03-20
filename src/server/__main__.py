from mcp.server.fastmcp import FastMCP

mcp = FastMCP("localsearch")

if __name__ == "__main__":
    mcp.run(transport="stdio")
