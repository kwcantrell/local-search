import asyncio
import sys

from .main import run

if __name__ == "__main__":
    print(asyncio.run(run(sys.argv[1])))
