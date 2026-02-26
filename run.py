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
import shutil
import signal
import subprocess
from pathlib import Path

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

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
FRONTEND_DIR = BASE_DIR / "FRONTEND"
WINDOWS_JOB = None


def env_flag(name: str, default: str = "1") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def ensure_runtime_requirements(hot_reload: bool) -> None:
    if hot_reload and importlib.util.find_spec("watchfiles") is None:
        raise RuntimeError(
            "HOT_RELOAD=1 requires 'watchfiles'. Install dependencies and retry: python -m pip install -r requirements.txt"
        )


def find_npm_command() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


def find_node_command() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


def ensure_frontend_requirements(frontend_hmr: bool) -> None:
    if not frontend_hmr:
        return
    if not (FRONTEND_DIR / "package.json").exists():
        raise RuntimeError(
            "FRONTEND_HMR=1 requires FRONTEND/package.json. Initialize frontend dependencies first."
        )
    if not find_npm_command():
        raise RuntimeError("FRONTEND_HMR=1 requires npm in PATH. Install Node.js and retry.")
    if not find_node_command():
        raise RuntimeError("FRONTEND_HMR=1 requires node in PATH. Install Node.js and retry.")


def ensure_frontend_deps_installed(frontend_hmr: bool) -> None:
    if not frontend_hmr:
        return
    vite_cmd = FRONTEND_DIR / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if vite_cmd.exists():
        return
    npm_cmd = find_npm_command()
    if not npm_cmd:
        raise RuntimeError("Cannot run npm install: npm not found in PATH.")
    print("Frontend dependencies not found. Running npm install in FRONTEND/ ...")
    result = subprocess.run([npm_cmd, "install"], cwd=str(FRONTEND_DIR), env=os.environ.copy())
    if result.returncode != 0:
        raise RuntimeError("npm install failed in FRONTEND/. Fix npm errors and retry.")


def setup_windows_kill_on_close_job():
    if os.name != "nt":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        wintypes.INT,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JobObjectExtendedLimitInformation = 9

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(job)
        return None
    return job


def assign_process_to_windows_job(proc: subprocess.Popen, job) -> None:
    if os.name != "nt" or not job:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    process_handle = wintypes.HANDLE(int(proc._handle))
    ok = kernel32.AssignProcessToJobObject(job, process_handle)
    if not ok:
        err = ctypes.get_last_error()
        print(f"Warning: failed to assign process to Windows Job Object (error={err})")


def close_windows_job(job) -> None:
    if os.name != "nt" or not job:
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle(job)


def start_vite(frontend_hmr: bool) -> subprocess.Popen | None:
    if not frontend_hmr:
        return None
    node_cmd = find_node_command()
    if not node_cmd:
        return None
    vite_cli = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite_cli.exists():
        raise RuntimeError("Vite CLI not found after npm install. Reinstall frontend dependencies.")
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
    proc = subprocess.Popen(
        [node_cmd, str(vite_cli), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
        cwd=str(FRONTEND_DIR),
        env=os.environ.copy(),
        creationflags=creationflags,
    )
    assign_process_to_windows_job(proc, WINDOWS_JOB)
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

    WINDOWS_JOB = setup_windows_kill_on_close_job()
    hot_reload = env_flag("HOT_RELOAD", "1")
    frontend_hmr = env_flag("FRONTEND_HMR", "1")
    ensure_runtime_requirements(hot_reload)
    ensure_frontend_requirements(frontend_hmr)
    ensure_frontend_deps_installed(frontend_hmr)

    vite_proc = start_vite(frontend_hmr)
    reload_dirs = [str(BASE_DIR / "BACKEND"), str(BASE_DIR / "FRONTEND")]
    reload_includes = ["main.py", "run.py", "BACKEND/*", "FRONTEND/*"]
    try:
        uvicorn.run(
            "main:app",
            host=HOST,
            port=PORT,
            reload=hot_reload,
            reload_dirs=reload_dirs if hot_reload else None,
            reload_includes=reload_includes if hot_reload else None,
        )
    finally:
        stop_process(vite_proc)
        close_windows_job(WINDOWS_JOB)
