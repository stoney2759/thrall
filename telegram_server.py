import asyncio
import sys
import warnings

if sys.platform == "win32":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from bootstrap.startup import start
from transports.telegram.bot import run

if __name__ == "__main__":
    start()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
        sys.exit(0)
