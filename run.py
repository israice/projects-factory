#!/usr/bin/env python3
"""
GitHub Projects Manager - Simplified Version

Run with:
    python run.py

Or directly with uvicorn:
    uvicorn main:app --reload --port 5999
"""

import os
import sys
from pathlib import Path

# Prevent creating __pycache__ when launching via run.py
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

PORT = int(os.getenv("PORT", "5999"))
HOST = os.getenv("HOST", "127.0.0.1")

if __name__ == "__main__":
    import uvicorn
    from main import app

    uvicorn.run(app, host=HOST, port=PORT, reload=False)
