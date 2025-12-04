"""Worker API for managing the worker service."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from app.services.proxy_agent import proxy_agent
from app.core.logging import setup_logging, LOG_FORMAT

print(f"DEBUG: LOG_FORMAT is: {LOG_FORMAT}")

async def main():
    """Start the ProxyAgent worker service."""
    setup_logging()
    import signal

    # Create a stop event
    stop_event = asyncio.Event()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    def handle_signal(sig):
        print(f"DEBUG: Received signal {sig}")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    import logging
    logger = logging.getLogger("worker_api")

    try:
        await proxy_agent.startup()

        # Wait for stop signal
        logger.warning("DEBUG: Waiting for stop signal...")
        while not stop_event.is_set():
            await asyncio.sleep(1)
        logger.warning("DEBUG: Stop signal received!")
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.warning("DEBUG: KeyboardInterrupt or CancelledError")
        pass
    except BaseException as e:
        import traceback
        logger.error(f"CRITICAL ERROR (BaseException) in main: {e}")
        traceback.print_exc()
    finally:
        logger.warning("DEBUG: Entering finally block")
        await proxy_agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())