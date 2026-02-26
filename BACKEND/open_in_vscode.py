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
