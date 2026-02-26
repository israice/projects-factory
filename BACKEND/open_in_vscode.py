#!/usr/bin/env python3
"""
Open a folder in VS Code from CLI.

Usage:
  python BACKEND/open_in_vscode.py <folder_path>
"""

from __future__ import annotations

import subprocess
import sys
import shutil
import os
import time
from pathlib import Path


def find_code_command() -> str | None:
    # 1) Prefer Microsoft VS Code explicit install paths
    local_app_data = os.getenv("LOCALAPPDATA", "")
    vscode_candidates = [
        Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
        Path(local_app_data) / "Programs" / "Microsoft VS Code" / "bin" / "code",
    ]
    for candidate in vscode_candidates:
        if candidate.exists():
            return str(candidate)

    # 2) Then PATH entries for VS Code command
    for cmd in ("code.cmd", "code"):
        found = shutil.which(cmd)
        if found:
            # Avoid selecting Cursor's shim if another code command is present first.
            if "cursor" not in found.lower():
                return found
    return None


def vscode_version_ok(code_cmd: str | None) -> bool:
    if not code_cmd:
        return False
    try:
        r = subprocess.run(
            [code_cmd, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        return r.returncode == 0
    except Exception:
        return False


def install_vscode_windows() -> tuple[bool, str]:
    winget = shutil.which("winget")
    if not winget:
        return False, "winget not found; cannot auto-install VS Code"
    try:
        r = subprocess.run(
            [
                winget,
                "install",
                "--id",
                "Microsoft.VisualStudioCode",
                "-e",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=900,
        )
        if r.returncode == 0:
            return True, ""
        detail = (r.stderr or r.stdout or "").strip()
        return False, detail[:400]
    except Exception as e:
        return False, str(e)


def ensure_vscode_command() -> tuple[str | None, str]:
    cmd = find_code_command()
    if vscode_version_ok(cmd):
        return cmd, ""

    if sys.platform != "win32":
        return None, "VS Code is not installed or `code --version` failed"

    ok, err = install_vscode_windows()
    if not ok:
        return None, f"Failed to install VS Code: {err or 'unknown error'}"

    # VS Code was installed; verify CLI availability and executable health.
    cmd = find_code_command()
    if not vscode_version_ok(cmd):
        return None, "VS Code installed, but `code --version` is still unavailable"
    return cmd, ""


def _list_windows_for_pid(pid: int) -> list[int]:
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    handles: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        win_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
        if int(win_pid.value) == int(pid):
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc, 0)
    return handles


def _force_foreground_maximize(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    import ctypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    sw_showmaximized = 3
    hwnd_topmost = -1
    hwnd_notopmost = -2
    swp_nosize = 0x0001
    swp_nomove = 0x0002
    swp_showwindow = 0x0040

    foreground = user32.GetForegroundWindow()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    target_tid = user32.GetWindowThreadProcessId(hwnd, None)

    attached_fg = False
    attached_target = False
    try:
        if fg_tid and fg_tid != cur_tid:
            attached_fg = bool(user32.AttachThreadInput(fg_tid, cur_tid, True))
        if target_tid and target_tid != cur_tid:
            attached_target = bool(user32.AttachThreadInput(target_tid, cur_tid, True))

        user32.ShowWindow(hwnd, sw_showmaximized)
        user32.BringWindowToTop(hwnd)
        user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_nosize | swp_nomove | swp_showwindow)
        user32.SetWindowPos(hwnd, hwnd_notopmost, 0, 0, 0, 0, swp_nosize | swp_nomove | swp_showwindow)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached_target:
            user32.AttachThreadInput(target_tid, cur_tid, False)
        if attached_fg:
            user32.AttachThreadInput(fg_tid, cur_tid, False)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Path argument is required", file=sys.stderr)
        return 1

    target = Path(argv[1]).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print("Target folder does not exist", file=sys.stderr)
        return 1

    cmd, err = ensure_vscode_command()
    if not cmd:
        print(err or "VS Code CLI is unavailable", file=sys.stderr)
        return 1

    launch_cmd = [cmd, str(target)]
    if sys.platform == "win32":
        # Open immediately in maximized state when possible.
        launch_cmd = [cmd, "--new-window", "--maximized", str(target)]
        before_windows = set()
        for proc in ("Code.exe", "Code - Insiders.exe"):
            r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {proc}", "/FO", "CSV", "/NH"], capture_output=True, text=True)
            for line in (r.stdout or "").splitlines():
                if not line or line.startswith("INFO:"):
                    continue
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[1].isdigit():
                    before_windows.update(_list_windows_for_pid(int(parts[1])))

    try:
        subprocess.run(launch_cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if sys.platform == "win32":
            detail = ((e.stderr or "") + "\n" + (e.stdout or "")).lower()
            if "unknown option" in detail or "unrecognized option" in detail:
                try:
                    subprocess.run([cmd, str(target)], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e2:
                    detail2 = (e2.stderr or e2.stdout or str(e2)).strip()
                    print(f"Failed to open in VS Code: {detail2[:300]}", file=sys.stderr)
                    return 1
                print(f"Opened in VS Code: {target}")
                return 0
        detail = (e.stderr or e.stdout or str(e)).strip()
        print(f"Failed to open in VS Code: {detail[:300]}", file=sys.stderr)
        return 1

    if sys.platform == "win32":
        deadline = time.time() + 4.0
        selected = None
        while time.time() < deadline:
            time.sleep(0.05)
            current_windows = set()
            for proc in ("Code.exe", "Code - Insiders.exe"):
                r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {proc}", "/FO", "CSV", "/NH"], capture_output=True, text=True)
                for line in (r.stdout or "").splitlines():
                    if not line or line.startswith("INFO:"):
                        continue
                    parts = [p.strip('"') for p in line.split('","')]
                    if len(parts) >= 2 and parts[1].isdigit():
                        current_windows.update(_list_windows_for_pid(int(parts[1])))
            new_windows = [w for w in current_windows if w not in before_windows]
            if new_windows:
                selected = new_windows[-1]
                break
            if current_windows:
                selected = list(current_windows)[-1]
        if selected:
            _force_foreground_maximize(selected)

    print(f"Opened in VS Code: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
