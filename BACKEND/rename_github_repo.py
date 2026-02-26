#!/usr/bin/env python3
"""
Rename a GitHub repository using the GitHub API, then update local YAML + local folder.

Usage:
  python rename_github_repo.py <old_name> <new_name>

Or via environment variables (.env supported):
  - GITHUB_TOKEN (required)
  - GITHUB_OWNER (default: 'israice')
  - OLD_REPO_NAME
  - NEW_REPO_NAME

Behavior preserved from the original script:
- Renames repo via GitHub API PATCH /repos/{owner}/{old_name} with {"name": new_name}
- On success (HTTP 200):
  - prints OK + new URL
  - updates BACKEND/get_all_github_projects.yaml (if present)
  - renames local folder under MY_REPOS (by direct folder name match, else scan git remotes)
  - attempts to set remote origin URL to https://github.com/{owner}/{new}.git (best-effort)
- On failure:
  - prints an error and exits with code 1
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv


DEFAULT_OWNER = "israice"
GITHUB_API_BASE = "https://api.github.com"


def get_project_root() -> Path:
    """Project root = parent of the directory containing this script."""
    return Path(__file__).resolve().parent.parent


def load_config(argv: list[str]) -> tuple[str, str, str, str]:
    """
    Returns (token, owner, old_name, new_name)
    CLI args override env, matching original behavior.
    """
    load_dotenv()

    token = os.getenv("GITHUB_TOKEN", "")
    owner = os.getenv("GITHUB_OWNER", DEFAULT_OWNER)

    if len(argv) >= 3:
        old_name = argv[1]
        new_name = argv[2]
    else:
        old_name = os.getenv("OLD_REPO_NAME", "")
        new_name = os.getenv("NEW_REPO_NAME", "")

    return token, owner, old_name, new_name


def build_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            # "token <PAT>" still works, but Bearer is the modern form.
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "rename-github-repo/1.0",
        }
    )
    return s


def update_yaml_file(project_root: Path, old_name: str, new_name: str) -> bool:
    """Update BACKEND/get_all_github_projects.yaml if present."""
    yaml_path = project_root / "BACKEND" / "get_all_github_projects.yaml"

    if not yaml_path.exists():
        print(f"Warning: YAML file not found at {yaml_path}")
        return False

    try:
        import yaml  # local import like original

        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        repos = data.get("repositories", [])
        if not isinstance(repos, list):
            print("Error updating YAML file: invalid YAML structure (repositories is not a list)")
            return False

        found = False
        for repo in repos:
            if isinstance(repo, dict) and repo.get("name") == old_name:
                repo["name"] = new_name

                old_url = repo.get("url", "")
                # Preserve original intent: update URL only if it ends with old_name.
                if isinstance(old_url, str) and old_url.endswith(old_name):
                    repo["url"] = old_url[: -len(old_name)] + new_name

                found = True
                break

        if not found:
            print(f"Warning: Repository '{old_name}' not found in YAML file")
            return False

        yaml_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        print(f"OK: Updated YAML file: {old_name} -> {new_name}")
        return True

    except Exception as e:
        print(f"Error updating YAML file: {e}")
        return False


def _git_remote_origin(folder_path: Path) -> Optional[str]:
    """Return origin URL for a git repo folder, or None."""
    try:
        r = subprocess.run(
            ["git", "-C", str(folder_path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip() or None
    except Exception:
        pass
    return None


def _matches_repo_name_in_remote(remote_url: str, old_name: str) -> bool:
    """Match original heuristic: remote ends with old_name or old_name + '.git'."""
    return remote_url.endswith(old_name) or remote_url.endswith(old_name + ".git")


def rename_local_folder(project_root: Path, owner: str, old_name: str, new_name: str) -> bool:
    """
    Rename the local folder in MY_REPOS.
    - First try MY_REPOS/old_name
    - Else scan all folders with .git and compare origin URL suffix (old_name / old_name.git)
    - If found: rename folder to MY_REPOS/new_name
    - Best-effort: update origin URL to https://github.com/{owner}/{new_name}.git
    """
    my_repos_dir = project_root / "MY_REPOS"
    if not my_repos_dir.exists():
        return True

    found_path: Optional[Path] = None

    direct_path = my_repos_dir / old_name
    if direct_path.exists():
        found_path = direct_path
    else:
        print(f"Searching for local folder matching repository '{old_name}'...")
        try:
            for entry in my_repos_dir.iterdir():
                if not entry.is_dir():
                    continue
                if not (entry / ".git").exists():
                    continue

                remote = _git_remote_origin(entry)
                if remote and _matches_repo_name_in_remote(remote, old_name):
                    found_path = entry
                    print(f"Found matching folder: {entry.name}")
                    break
        except Exception:
            # Preserve original "best-effort" scanning behavior.
            found_path = None

    if not found_path:
        print(f"Info: No local folder found for repository '{old_name}'")
        return True

    new_path = my_repos_dir / new_name

    try:
        found_path.rename(new_path)
        print(f"OK: Renamed local folder: {found_path.name} -> {new_name}")

        # Best-effort update remote.
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(new_path),
                    "remote",
                    "set-url",
                    "origin",
                    f"https://github.com/{owner}/{new_name}.git",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            print("OK: Updated git remote URL")
        except Exception as e:
            print(f"Warning: Could not update git remote: {e}")

        return True

    except Exception as e:
        print(f"Error renaming local folder: {e}")
        return False


def rename_repository(token: str, owner: str, old_name: str, new_name: str) -> bool:
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        return False

    if not old_name or not new_name:
        print("Error: OLD_REPO_NAME and NEW_REPO_NAME are required.")
        return False

    print(f"Renaming repository: {owner}/{old_name} -> {owner}/{new_name}")

    api_url = f"{GITHUB_API_BASE}/repos/{owner}/{old_name}"
    session = build_session(token)

    try:
        resp = session.patch(api_url, json={"name": new_name}, timeout=30)

        if resp.status_code == 200:
            print(f"OK: Successfully renamed repository to '{new_name}'")
            print(f"New URL: https://github.com/{owner}/{new_name}")

            project_root = get_project_root()
            update_yaml_file(project_root, old_name, new_name)
            rename_local_folder(project_root, owner, old_name, new_name)
            return True

        # Improve error diagnostics without changing success criteria.
        try:
            payload = resp.json()
        except Exception:
            payload = None
        msg = payload.get("message") if isinstance(payload, dict) else (resp.text or "").strip()
        print(f"Error: Failed to rename repository (Status: {resp.status_code})")
        if msg:
            print(f"Details: {msg}")
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error: Network error occurred: {e}")
        return False


if __name__ == "__main__":
    token, owner, old_name, new_name = load_config(sys.argv)
    success = rename_repository(token, owner, old_name, new_name)
    raise SystemExit(0 if success else 1)