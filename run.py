#!/usr/bin/env python3
"""
GitHub Projects Manager - FastAPI Server

Run with:
    python run.py

Or directly with uvicorn:
    uvicorn BACKEND.api.main:app --reload --port 5999
"""

import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PORT = int(os.getenv("PORT", "5999"))

if __name__ == "__main__":
    import uvicorn
    
    print(f"🚀 Starting GitHub Projects Manager on http://127.0.0.1:{PORT}")
    print(f"📁 Project root: {BASE_DIR}")
    
    uvicorn.run(
        "BACKEND.api.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info",
    )
