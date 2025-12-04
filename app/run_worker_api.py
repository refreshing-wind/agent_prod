"""Worker service entry point."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from app.api.worker_api import main

if __name__ == "__main__":
    asyncio.run(main())
