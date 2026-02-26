#!/usr/bin/env python3
"""
Install (git clone) one or more GitHub repositories into project_root/MY_REPOS.

Preserves the original observable behavior:
- If no repo URLs are provided, clones https://github.com/israice/Create-Project-Folder.git
- Clones into ../MY_REPOS/<repo_name>
- If target directory exists: skip
- Produces per-repo result dicts with keys: name, url, path, status (+ error on failures)
- Prints an INSTALLATION SUMMARY unless --json is provided
- IMPORTANT: --json is NOT treated as a repo URL (fixes original bug)

Cross-platform:
- Works on Windows/macOS/Linux, provided `git` is available in PATH.

Notes:
- Repo name parsing is more robust (supports .git, trailing slashes, and scp-like git@host:org/repo.git).
- Uses subprocess with captured stderr for better error messages.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


DEFAULT_REPO = "https://github.com/israice/Create-Project-Folder.git"


def _ensure_utf8_stdio_on_windows() -> None:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _project_root_from_script() -> Path:
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def _require_git() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("git was not found in PATH. Please install Git and try again.")


def _repo_name_from_url(repo_url: str) -> str:
    """
    Supports:
    - https://github.com/org/repo.git
    - https://github.com/org/repo/
    - git@github.com:org/repo.git
    - ssh://git@github.com/org/repo.git
    """
    u = repo_url.strip()

    # Normalize trailing slash
    u = u.rstrip("/")

    # Handle scp-like syntax: git@github.com:org/repo(.git)
    m = re.search(r":([^/]+)/([^/]+)$", u)
    if m:
        name = m.group(2)
    else:
        # Regular URL/path-like
        name = u.split("/")[-1]

    if name.endswith(".git"):
        name = name[:-4]

    if not name:
        raise ValueError(f"Could not determine repository name from URL: {repo_url}")

    return name


def clone_repository(repo_url: str, target_path: Path) -> None:
    if target_path.exists():
        print(f"⚠️  Directory '{target_path}' already exists. Skipping...")
        return

    print(f"📥 Cloning {repo_url} into {target_path}...")

    # Capture output so errors are readable and we can still show them.
    proc = subprocess.run(
        ["git", "clone", repo_url, str(target_path)],
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        details = (proc.stderr or proc.stdout or "").strip()
        raise subprocess.CalledProcessError(proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr) from None

    print("✅ Repository cloned successfully!")


def install_repo(repo_url: str, my_repos_dir: Path) -> tuple[Path, str]:
    repo_name = _repo_name_from_url(repo_url)
    target_path = my_repos_dir / repo_name

    if target_path.exists():
        return target_path, "skipped"

    clone_repository(repo_url, target_path)
    return target_path, "installed"


def main(repo_urls: Optional[list[str]] = None, as_json: bool = False) -> list[dict]:
    _require_git()

    project_root = _project_root_from_script()
    my_repos_dir = project_root / "MY_REPOS"
    my_repos_dir.mkdir(exist_ok=True)

    if not repo_urls:
        repo_urls = [DEFAULT_REPO]

    results: list[dict] = []
    verbose = not as_json  # keep JSON clean

    for repo_url in repo_urls:
        if verbose:
            print("-" * 60)

        try:
            target_path, status = install_repo(repo_url, my_repos_dir)
            repo_name = target_path.name

            if status == "skipped":
                if verbose:
                    print(f"⚠️  Repository '{repo_name}' already exists. Skipping.")
                results.append(
                    {"name": repo_name, "url": repo_url, "path": str(target_path), "status": "skipped"}
                )
            else:
                if verbose:
                    print(f"✅ Installation complete for '{repo_name}'!")
                    print(f"📁 Repository location: {target_path}")
                results.append(
                    {"name": repo_name, "url": repo_url, "path": str(target_path), "status": "success"}
                )

        except subprocess.CalledProcessError as e:
            # Make error readable; include stderr when available.
            stderr = getattr(e, "stderr", None)
            err_text = (stderr or str(e)).strip()
            if verbose:
                print(f"❌ Error during installation: {err_text}")
            results.append({"name": repo_url, "url": repo_url, "path": "", "status": "error", "error": err_text})

        except Exception as e:
            err_text = str(e).strip()
            if verbose:
                print(f"❌ Unexpected error: {err_text}")
            results.append({"name": repo_url, "url": repo_url, "path": "", "status": "error", "error": err_text})

    return results


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Clone Git repositories into ../MY_REPOS.")
    p.add_argument("repo_urls", nargs="*", help="Repository URLs to clone.")
    p.add_argument("--json", action="store_true", help="Output results as JSON.")
    return p.parse_args(argv)


if __name__ == "__main__":
    _ensure_utf8_stdio_on_windows()

    args = parse_args(sys.argv[1:])
    results = main(args.repo_urls, as_json=args.json)

    if args.json:
        print(json.dumps(results, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print("INSTALLATION SUMMARY")
        print("=" * 60)
        for result in results:
            if result["status"] == "success":
                status_icon, status_text = "✅", "installed"
            elif result["status"] == "skipped":
                status_icon, status_text = "⚠️", "skipped (already exists)"
            else:
                status_icon, status_text = "❌", "error"

            print(f"{status_icon} {result['name']}: {status_text}")

            if result["status"] in ("success", "skipped"):
                print(f"   Location: {result['path']}")
            elif "error" in result:
                print(f"   Error: {result['error']}")