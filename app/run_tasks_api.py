"""API Server entry point."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from app.api.tasks_api import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
