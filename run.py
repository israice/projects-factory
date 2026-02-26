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
import importlib.util
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


def env_flag(name: str, default: str = "1") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def ensure_runtime_requirements(hot_reload: bool) -> None:
    if hot_reload and importlib.util.find_spec("watchfiles") is None:
        raise RuntimeError(
            "HOT_RELOAD=1 requires 'watchfiles'. Install dependencies and retry: python -m pip install -r requirements.txt"
        )


if __name__ == "__main__":
    import uvicorn
    hot_reload = env_flag("HOT_RELOAD", "1")
    ensure_runtime_requirements(hot_reload)
    reload_dirs = [str(BASE_DIR / "BACKEND"), str(BASE_DIR / "FRONTEND")]
    reload_includes = ["main.py", "run.py", "BACKEND/*", "FRONTEND/*"]
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=hot_reload,
        reload_dirs=reload_dirs if hot_reload else None,
        reload_includes=reload_includes if hot_reload else None,
    )
