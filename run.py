#!/usr/bin/env python3
"""
GitHub Projects Manager - Dev Runner

Starts:
- FastAPI backend (uvicorn, reload)
- Vite frontend dev server (HMR)
"""

import importlib.util
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "FRONTEND"
SETTINGS_PATH = BASE_DIR / "settings.yaml"
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()


def load_server_settings() -> tuple[int, str]:
    default_port = int(os.getenv("PORT", "5999"))
    default_host = os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1"

    if not SETTINGS_PATH.exists():
        return default_port, default_host

    try:
        import yaml
        raw = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return default_port, default_host

    if not isinstance(raw, dict):
        return default_port, default_host

    server = raw.get("server") or {}
    if not isinstance(server, dict):
        return default_port, default_host

    try:
        port = int(server.get("port", default_port))
    except Exception:
        port = default_port
    if port < 1:
        port = default_port

    host = str(server.get("host", default_host)).strip() or default_host
    return port, host


PORT, HOST = load_server_settings()


def env_flag(name: str, default: str = "1") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def ensure_backend_requirements(hot_reload: bool) -> None:
    if hot_reload and importlib.util.find_spec("watchfiles") is None:
        raise RuntimeError(
            "HOT_RELOAD=1 requires 'watchfiles'. Install dependencies and retry: python -m pip install -r requirements.txt"
        )


def npm_cmd() -> str:
    cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not cmd:
        raise RuntimeError("Node.js/npm is required for frontend HMR. Install Node.js and retry.")
    return cmd


def node_cmd() -> str:
    cmd = shutil.which("node") or shutil.which("node.exe")
    if not cmd:
        raise RuntimeError("Node.js is required for frontend HMR. Install Node.js and retry.")
    return cmd


def ensure_frontend_deps() -> None:
    pkg = FRONTEND_DIR / "package.json"
    vite_cli = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if not pkg.exists():
        raise RuntimeError("Missing FRONTEND/package.json")
    if vite_cli.exists():
        return
    print("Frontend dependencies not found. Running npm install in FRONTEND/ ...")
    result = subprocess.run([npm_cmd(), "install"], cwd=str(FRONTEND_DIR), env=os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError("npm install failed in FRONTEND/")


def wait_for_backend_listener(host: str, port: int, timeout_sec: float = 30.0) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def start_vite() -> subprocess.Popen:
    vite_cli = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    env = os.environ.copy()
    env["PF_BACKEND_HOST"] = HOST
    env["PF_BACKEND_PORT"] = str(PORT)
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    proc = subprocess.Popen(
        [node_cmd(), str(vite_cli), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        cwd=str(FRONTEND_DIR),
        env=env,
        creationflags=creationflags,
    )
    print("Frontend HMR: http://127.0.0.1:5173")
    return proc


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    if env_flag("BITWARDEN_ENABLED", "0"):
        provider = os.getenv("BITWARDEN_PROVIDER", "auto").strip().lower() or "auto"
        if provider == "auto":
            provider = "bws" if bool(os.getenv("BWS_ACCESS_TOKEN", "").strip()) else "bw"
        if provider == "bws":
            from BACKEND.bitwarden_env import inject_github_env_from_bws, verify_bws_capabilities

            bws_project_id = os.getenv("BWS_PROJECT_ID", "").strip() or None
            token_key = os.getenv("BWS_GITHUB_TOKEN_SECRET", "GITHUB_TOKEN").strip() or "GITHUB_TOKEN"
            username_key = os.getenv("BWS_GITHUB_USERNAME_SECRET", "GITHUB_USERNAME").strip() or "GITHUB_USERNAME"
            require_write = env_flag("BWS_REQUIRE_WRITE", "1")

            verify_bws_capabilities(require_write=require_write, project_id=bws_project_id)
            inject_github_env_from_bws(
                project_id=bws_project_id,
                token_key=token_key,
                username_key=username_key,
            )
            print("Bitwarden secrets loaded via bws.")
            print(f"BWS write probe: {'enabled' if require_write else 'disabled'}")
        elif provider == "bw":
            from BACKEND.bitwarden_env import inject_github_env_from_bw

            bw_item = os.getenv("BITWARDEN_ITEM", "projects-factory/github").strip() or "projects-factory/github"
            inject_github_env_from_bw(bw_item)
            print(f"Bitwarden secrets loaded from item: {bw_item}")
        else:
            raise RuntimeError("Unsupported BITWARDEN_PROVIDER. Use 'auto', 'bws', or 'bw'.")
        print(f"GITHUB_TOKEN present: {'yes' if bool(os.getenv('GITHUB_TOKEN', '').strip()) else 'no'}")
    else:
        print("Bitwarden secrets disabled (BITWARDEN_ENABLED=0)")
        print(f"GITHUB_TOKEN present: {'yes' if bool(os.getenv('GITHUB_TOKEN', '').strip()) else 'no'}")

    hot_reload = env_flag("HOT_RELOAD", "1")
    ensure_backend_requirements(hot_reload)
    ensure_frontend_deps()

    vite_holder = {"proc": None, "stop": False}

    def vite_worker() -> None:
        if wait_for_backend_listener(HOST, PORT, timeout_sec=30.0):
            if not vite_holder["stop"]:
                vite_holder["proc"] = start_vite()

    thread = threading.Thread(target=vite_worker, daemon=True, name="vite-worker")
    thread.start()

    # Watch backend code only; ignore repository content changes in MY_REPOS/NEW_PROJECTS.
    reload_dirs = [str(BASE_DIR / "BACKEND")]
    reload_includes = ["*.py"]
    try:
        uvicorn.run(
            "BACKEND.main:app",
            host=HOST,
            port=PORT,
            reload=hot_reload,
            reload_dirs=reload_dirs if hot_reload else None,
            reload_includes=reload_includes if hot_reload else None,
        )
    finally:
        vite_holder["stop"] = True
        if thread.is_alive():
            thread.join(timeout=1.0)
        stop_process(vite_holder.get("proc"))
