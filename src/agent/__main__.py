import asyncio
import sys

from .main import run

if __name__ == "__main__":
    result = asyncio.run(run(sys.argv[1]))
    print("Tool called: mcp__localsearch__echo")
    print(f"Result: {result}")
