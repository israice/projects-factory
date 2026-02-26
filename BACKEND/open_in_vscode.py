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

    # 3) Fallback to Cursor only if VS Code is unavailable
    cursor_candidates = [
        Path(local_app_data) / "Programs" / "cursor" / "resources" / "app" / "codeBin" / "code.cmd",
        Path(local_app_data) / "Programs" / "cursor" / "resources" / "app" / "codeBin" / "code",
    ]
    for candidate in cursor_candidates:
        if candidate.exists():
            return str(candidate)

    for cmd in ("cursor.cmd", "cursor"):
        found = shutil.which(cmd)
        if found:
            return found
    return None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Path argument is required", file=sys.stderr)
        return 1

    target = Path(argv[1]).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        print("Target folder does not exist", file=sys.stderr)
        return 1

    cmd = find_code_command()
    if not cmd:
        print("VS Code CLI was not found (code/cursor). Add it to PATH or install VS Code/Cursor.", file=sys.stderr)
        return 1

    try:
        subprocess.run([cmd, str(target)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or e.stdout or str(e)).strip()
        print(f"Failed to open in VS Code: {detail[:300]}", file=sys.stderr)
        return 1

    print(f"Opened in VS Code: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
