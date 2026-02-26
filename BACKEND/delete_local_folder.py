#!/usr/bin/env python3
"""
Delete one or more local repository folders from project_root/MY_REPOS or project_root/NEW_PROJECTS.

Behavior goals (kept from the original):
- Accept repository names as positional args.
- Optionally output JSON via --json (and NOT treat --json as a repo name).
- Search order: MY_REPOS first, then NEW_PROJECTS.
- Return per-repo status: success | not_found | error and a message.
- Print a human-friendly summary when not using --json.
- Work on Windows and non-Windows.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Optional


def _ensure_utf8_stdio_on_windows() -> None:
    # Preserve the original intent: avoid UnicodeEncodeError in Windows console.
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _is_safe_repo_name(name: str) -> bool:
    """
    Reject anything that can escape the intended directories.
    We treat repo_name as a folder name, not a path.
    """
    if not name or name.strip() != name:
        return False

    # Disallow path separators, drive letters, traversal, and absolute paths.
    p = Path(name)
    if p.is_absolute():
        return False
    if any(part in ("..", ".") for part in p.parts):
        return False
    if len(p.parts) != 1:
        return False

    # Also block Windows drive-like patterns (e.g., "C:foo" or "C:").
    if sys.platform == "win32" and ":" in name:
        return False

    return True


def _onerror_rmtree(func, path, exc_info):
    """
    Robust rmtree handler: if a file is read-only, make it writable and retry.
    This helps on Windows and sometimes on macOS/Linux too.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        # Re-raise the original exception
        raise


def _windows_rmdir_tree(target_path: Path) -> tuple[bool, str]:
    """
    Prefer 'rmdir /S /Q' for Windows to handle odd locked file cases.
    Return (success, diagnostics_message).
    """
    # Remove read-only, system, hidden attributes recursively (best-effort).
    # Use cmd /c so Windows built-ins behave consistently.
    diag = []

    try:
        # attrib needs a wildcard to affect contents reliably.
        # Example: attrib -R -S -H /S /D "C:\path\*"
        wildcard = str(target_path / "*")
        r = subprocess.run(
            ["cmd", "/c", "attrib", "-R", "-S", "-H", "/S", "/D", wildcard],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.stdout:
            diag.append(r.stdout.strip())
        if r.stderr:
            diag.append(r.stderr.strip())
    except subprocess.TimeoutExpired:
        diag.append("attrib timed out (continuing)")

    try:
        r = subprocess.run(
            ["cmd", "/c", "rmdir", "/S", "/Q", str(target_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.stdout:
            diag.append(r.stdout.strip())
        if r.stderr:
            diag.append(r.stderr.strip())

        # rmdir returns non-zero on failure; treat that as failure.
        if r.returncode != 0:
            return False, "; ".join([d for d in diag if d]) or f"rmdir failed with code {r.returncode}"

        return True, "; ".join([d for d in diag if d]) or "deleted"
    except subprocess.TimeoutExpired:
        return False, "Deletion timed out"
    except Exception as e:
        return False, str(e)


def delete_repository(
    repo_name: str,
    my_repos_dir: Path,
    new_projects_dir: Optional[Path] = None,
    verbose: bool = True,
) -> tuple[str, str, str]:
    """
    Delete a repository folder from MY_REPOS or NEW_PROJECTS.

    Returns: (repo_name, status, message)
    status ∈ {"success", "not_found", "error"}
    """
    if not _is_safe_repo_name(repo_name):
        return repo_name, "error", "Invalid repository name (must be a single folder name, no paths)."

    # Search order: MY_REPOS first, then NEW_PROJECTS (kept).
    target_path = my_repos_dir / repo_name
    if not target_path.exists() and new_projects_dir:
        target_path = new_projects_dir / repo_name

    if not target_path.exists():
        return repo_name, "not_found", f"Directory '{repo_name}' does not exist in MY_REPOS or NEW_PROJECTS."

    if not target_path.is_dir():
        return repo_name, "error", f"'{target_path}' is not a directory."

    if verbose:
        print(f"🗑️  Deleting {target_path}...")

    try:
        if sys.platform == "win32":
            ok, diag = _windows_rmdir_tree(target_path)
            if not ok:
                # If it still exists, report failure.
                if target_path.exists():
                    return repo_name, "error", diag
            # Sometimes the FS lags; double-check.
            if target_path.exists():
                return repo_name, "error", f"Failed to delete '{repo_name}'"
        else:
            shutil.rmtree(target_path, onerror=_onerror_rmtree)
            if target_path.exists():
                return repo_name, "error", f"Failed to delete '{repo_name}'"

        if verbose:
            print("✅ Repository deleted successfully!")
        return repo_name, "success", f"Deleted '{repo_name}'"

    except subprocess.TimeoutExpired:
        return repo_name, "error", "Deletion timed out"
    except Exception as e:
        if verbose:
            print(f"❌ Error during deletion: {e}")
        return repo_name, "error", str(e)


def main(repo_names: list[str], as_json: bool = False) -> list[dict]:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    my_repos_dir = project_root / "MY_REPOS"
    new_projects_dir = project_root / "NEW_PROJECTS"

    if not repo_names:
        print("❌ No repository names provided.")
        return []

    results: list[dict] = []
    verbose = not as_json  # keep JSON clean, like the intent of the original

    for repo_name in repo_names:
        if verbose:
            print("-" * 60)

        name, status, message = delete_repository(repo_name, my_repos_dir, new_projects_dir, verbose=verbose)
        results.append({"name": name, "status": status, "message": message})

        if verbose:
            if status == "success":
                print(f"✅ Deletion complete for '{name}'!")
            elif status == "not_found":
                print(f"⚠️  Repository '{name}' not found. Nothing to delete.")
            else:
                print(f"❌ {message}")

    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Delete local repository folders from MY_REPOS/NEW_PROJECTS.")
    p.add_argument("repos", nargs="*", help="Repository folder names to delete (not paths).")
    p.add_argument("--json", action="store_true", help="Output results as JSON.")
    return p.parse_args(argv)


if __name__ == "__main__":
    _ensure_utf8_stdio_on_windows()

    args = parse_args(sys.argv[1:])
    results = main(args.repos, as_json=args.json)

    if args.json:
        print(json.dumps(results, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print("DELETION SUMMARY")
        print("=" * 60)
        for result in results:
            if result["status"] == "success":
                status_icon, status_text = "✅", "deleted"
            elif result["status"] == "not_found":
                status_icon, status_text = "⚠️", "not found"
            else:
                status_icon, status_text = "❌", "error"

            print(f"{status_icon} {result['name']}: {status_text}")
            if result.get("message") and result["status"] != "success":
                print(f"   {result['message']}")