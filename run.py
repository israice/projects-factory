#!/usr/bin/env python3
"""
Flask UI for managing GitHub repos + local projects.

Preserves the original observable behavior:
- Serves FRONTEND as templates + static.
- "/" renders index.html with:
  - repos = GitHub repos from BACKEND/get_all_github_projects.yaml + NEW_PROJECTS folders
  - installed_repos = set of normalized origin URLs for git repos in MY_REPOS
  - installed_count = len(installed_repos)
  - count = len(github repos from YAML)  (not including NEW_PROJECTS)
  - username, avatar_url, message
- /refresh runs BACKEND/get_all_github_projects.py and redirects to /
- /create-new runs MY_REPOS/Create-Project-Folder/create_new_project.py and redirects with ?message=
- /install POST runs BACKEND/install_existing_repo.py <urls...> and returns JSON with output/error/installed_count
- /delete POST runs BACKEND/delete_local_folder.py <names...> and returns JSON with output/error/installed_count/new_projects_count
- /rename POST renames folder in NEW_PROJECTS and returns JSON
- /rename-github POST runs BACKEND/rename_github_repo.py old new and returns JSON
- Flask built-in reloader for development
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_hot_reload import HotReload

# Suppress requests dependency warning (not critical)
import logging
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('flask_hot_reload').setLevel(logging.WARNING)

try:
    import requests
except Exception:
    requests = None  # type: ignore[assignment]


# ---- Logging setup ----

# Configure logging
log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler],
)
logger = logging.getLogger(__name__)


# ---- Configuration ----

load_dotenv()

# Server ports from environment
DEFAULT_PORT = int(os.getenv("PORT", "5999"))
DEFAULT_LIVEPORT = int(os.getenv("LIVERELOAD_PORT", "35729"))

# Load timeouts from settings.yaml
SETTINGS_PATH = Path(__file__).resolve().parent / "settings.yaml"
DEFAULT_TIMEOUTS = {
    "refresh": 120,
    "create_project": 120,
    "install_per_repo": 300,
    "delete_per_repo": 60,
    "rename": 60,
    "git_remote": 5,
}


def load_timeouts() -> dict[str, int]:
    """Load timeout configuration from settings.yaml."""
    if not SETTINGS_PATH.exists():
        logger.warning(f"Settings file not found: {SETTINGS_PATH}, using defaults")
        return DEFAULT_TIMEOUTS
    
    try:
        data = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
        timeouts = data.get("timeouts", {})
        if not isinstance(timeouts, dict):
            return DEFAULT_TIMEOUTS
        
        return {
            "refresh": timeouts.get("refresh", DEFAULT_TIMEOUTS["refresh"]),
            "create_project": timeouts.get("create_project", DEFAULT_TIMEOUTS["create_project"]),
            "install_per_repo": timeouts.get("install_per_repo", DEFAULT_TIMEOUTS["install_per_repo"]),
            "delete_per_repo": timeouts.get("delete_per_repo", DEFAULT_TIMEOUTS["delete_per_repo"]),
            "rename": timeouts.get("rename", DEFAULT_TIMEOUTS["rename"]),
            "git_remote": timeouts.get("git_remote", DEFAULT_TIMEOUTS["git_remote"]),
        }
    except Exception as e:
        logger.error(f"Error loading settings.yaml: {e}, using defaults")
        return DEFAULT_TIMEOUTS


TIMEOUTS = load_timeouts()


# ---- Paths / app ----

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "FRONTEND"
BACKEND_DIR = BASE_DIR / "BACKEND"
MY_REPOS_DIR = BASE_DIR / "MY_REPOS"
NEW_PROJECTS_DIR = BASE_DIR / "NEW_PROJECTS"
YAML_PATH = BACKEND_DIR / "get_all_github_projects.yaml"

app = Flask(__name__, template_folder=str(FRONTEND_DIR), static_folder=str(FRONTEND_DIR))

# Initialize hot reload for all file types (Python, HTML, CSS, JS)
hot_reload = HotReload(app,
    includes=[
        str(FRONTEND_DIR),  # HTML, CSS, JS files
        str(BACKEND_DIR),   # Python scripts
        str(BASE_DIR),      # Root directory for run.py
    ],
    excludes=[
        '__pycache__',
        '.git',
        '.ruff_cache',
        '*.pyc',
        'NEW_PROJECTS',     # Exclude new project creation noise
        'MY_REPOS',         # Exclude installed repos
    ]
)


# ---- Helpers ----

@dataclass(frozen=True)
class Project:
    name: str
    url: str
    private: bool
    description: str
    created_at: str
    is_new_project: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "private": self.private,
            "description": self.description,
            "created_at": self.created_at,
            "is_new_project": self.is_new_project,
        }


def run_py(script_path: Path, args: list[str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """
    Run a Python script using the current interpreter (sys.executable).
    Captures output, returns CompletedProcess. Does not raise by default.

    The subprocess is tracked for proper cleanup on server shutdown.
    """
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd += args

    logger.debug(f"Running script: {script_path} with args: {args}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',  # Replace undecodable characters
        )
        logger.debug(f"Script {script_path} completed with returncode={result.returncode}")
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"Script {script_path} timed out after {timeout}s")
        raise


def get_installed_repo_urls(my_repos_dir: Path) -> set[str]:
    """Get set of normalized Git repo origin URLs from installed repositories in MY_REPOS."""
    installed: set[str] = set()
    if not my_repos_dir.exists():
        logger.debug(f"MY_REPOS directory does not exist: {my_repos_dir}")
        return installed

    for entry in my_repos_dir.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(entry), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=TIMEOUTS["git_remote"],
            )
            if result.returncode != 0:
                logger.debug(f"No origin URL found for {entry.name}")
                continue

            remote_url = (result.stdout or "").strip()
            if remote_url.endswith(".git"):
                remote_url = remote_url[:-4]
            installed.add(remote_url.rstrip("/"))
        except subprocess.TimeoutExpired:
            logger.warning(f"Git remote check timed out for {entry.name}")
        except Exception as e:
            logger.debug(f"Error checking git remote for {entry.name}: {e}")

    logger.info(f"Found {len(installed)} installed repositories")
    return installed


def get_new_projects(new_projects_dir: Path) -> list[dict[str, Any]]:
    """Get list of new projects from NEW_PROJECTS directory (as dicts, matching template expectations)."""
    projects: list[dict[str, Any]] = []
    if not new_projects_dir.exists():
        return projects

    for entry in new_projects_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            created_ts = entry.stat().st_ctime
            created_at = datetime.fromtimestamp(created_ts).isoformat() + "Z"
        except Exception:
            created_at = ""

        # Keep original intent: "url" is local path with forward slashes
        project_url = str(entry).replace("\\", "/")
        projects.append(
            Project(
                name=entry.name,
                url=project_url,
                private=False,
                description="Local project folder",
                created_at=created_at,
                is_new_project=True,
            ).as_dict()
        )

    return projects


def load_repos_from_yaml(yaml_path: Path) -> list[dict[str, Any]]:
    if not yaml_path.exists():
        # Original code would crash; keeping behavior *mostly* but giving a clearer error.
        # If you want strict parity, replace this with a hard exception.
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    repos = data.get("repositories", [])
    if not isinstance(repos, list):
        return []
    # Keep only dict entries
    return [r for r in repos if isinstance(r, dict)]


def fetch_avatar_url(username: str, token: str) -> str:
    # Preserve "best-effort": failures return "".
    if not username or requests is None:
        return ""
    try:
        headers = {"Authorization": f"token {token}"} if token else {}
        resp = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=5)
        if resp.status_code == 200:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload.get("avatar_url", "") or ""
    except Exception:
        pass
    return ""


def count_folders(dir_path: Path) -> int:
    if not dir_path.exists():
        return 0
    try:
        return sum(1 for p in dir_path.iterdir() if p.is_dir())
    except Exception:
        return 0


# ---- Routes ----

@app.after_request
def add_no_cache_headers(response):
    """Disable caching for all responses during development."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@app.route("/favicon.ico")
def favicon():
    return "", 204


@app.route("/.well-known/appspecific/com.chrome.devtools.json")
def chrome_devtools():
    """Return Chrome DevTools configuration."""
    return jsonify({
        "devtools": {
            "description": "Chrome DevTools configuration",
            "version": "1.0"
        }
    })


@app.route("/")
def index():
    """Main page - display all repositories."""
    load_dotenv()
    username = os.getenv("GITHUB_USERNAME", "Unknown")
    token = os.getenv("GITHUB_TOKEN", "")
    message = request.args.get("message", "")

    logger.debug(f"Loading index page for user: {username}")

    avatar_url = fetch_avatar_url(username, token)

    repos = load_repos_from_yaml(YAML_PATH)
    repos_sorted = sorted(
        repos,
        key=lambda r: (r.get("name") != username, str(r.get("name", "")).lower()),
    )

    installed_urls = get_installed_repo_urls(MY_REPOS_DIR)
    new_projects = get_new_projects(NEW_PROJECTS_DIR)

    all_projects = repos_sorted + new_projects

    logger.info(f"Serving index page with {len(all_projects)} projects ({len(repos_sorted)} GitHub, {len(new_projects)} local)")

    return render_template(
        "index.html",
        repos=all_projects,
        username=username,
        count=len(repos_sorted),            # keep original: only GitHub repos count
        installed_count=len(installed_urls),
        installed_repos=installed_urls,
        avatar_url=avatar_url,
        message=message,
    )


@app.route("/refresh")
def refresh():
    """Refresh GitHub repositories list by running get_all_github_projects.py."""
    logger.info("Starting repositories refresh")
    proc = run_py(BACKEND_DIR / "get_all_github_projects.py", timeout=TIMEOUTS["refresh"])
    if proc.returncode != 0:
        error_msg = (proc.stderr or proc.stdout or "Refresh failed").strip()
        logger.error(f"Refresh failed: {error_msg}")
        return redirect(url_for("index", message=f"❌ Refresh failed: {error_msg[:200]}"))
    logger.info("Repositories refreshed successfully")
    return redirect(url_for("index", message="✅ Repositories refreshed successfully"))


@app.route("/create-new")
def create_new():
    """Create new project folder by running create_new_project.py."""
    logger.info("Starting new project creation")
    proc = run_py(MY_REPOS_DIR / "Create-Project-Folder" / "create_new_project.py", timeout=TIMEOUTS["create_project"])
    if proc.returncode != 0:
        error_msg = (proc.stderr or proc.stdout or "Create project failed").strip()
        logger.error(f"Create project failed: {error_msg}")
        return redirect(url_for("index", message=f"❌ Create project failed: {error_msg[:200]}"))

    output = (proc.stdout or "").strip()
    logger.debug(f"Create project output: {output}")

    # Try to parse JSON output first
    folder_name = ""
    try:
        result = json.loads(output)
        if isinstance(result, dict) and result.get("success"):
            folder_name = result.get("folder_name", "")
            logger.info(f"Project created: {folder_name}")
    except json.JSONDecodeError:
        # Fallback to string parsing for backward compatibility
        if 'Project "' in output and '" created' in output:
            start = output.find('Project "') + len('Project "')
            end = output.find('" created')
            folder_name = output[start:end]

    message = f'Project "{folder_name}" created successfully' if folder_name else "Project created successfully"
    return redirect(url_for("index", message=message))


@app.route("/install", methods=["POST"])
def install():
    """Install selected repositories by running install_existing_repo.py."""
    data = request.get_json(silent=True) or {}
    repo_urls = data.get("repos", [])
    if not isinstance(repo_urls, list) or not repo_urls:
        return jsonify({"error": "No repositories selected"}), 400

    logger.info(f"Installing {len(repo_urls)} repositories")
    try:
        timeout = TIMEOUTS["install_per_repo"] * len(repo_urls)
        proc = run_py(BACKEND_DIR / "install_existing_repo.py", args=[str(u) for u in repo_urls], timeout=timeout)

        installed_count = count_folders(MY_REPOS_DIR)
        logger.info(f"Installation complete, total installed: {installed_count}")
        return jsonify(
            {
                "success": True,
                "output": proc.stdout,
                "error": proc.stderr if proc.returncode != 0 else None,
                "installed_count": installed_count,
            }
        )
    except subprocess.TimeoutExpired:
        logger.error("Installation timed out")
        return jsonify({"error": "Installation timed out. Try installing fewer repositories at once."}), 504
    except Exception as e:
        logger.error(f"Installation error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/delete", methods=["POST"])
def delete():
    """Delete selected repositories by running delete_local_folder.py."""
    data = request.get_json(silent=True) or {}
    repo_names = data.get("repos", [])
    if not isinstance(repo_names, list) or not repo_names:
        return jsonify({"error": "No repositories selected"}), 400

    logger.info(f"Deleting {len(repo_names)} repositories")
    try:
        timeout = TIMEOUTS["delete_per_repo"] * len(repo_names)
        proc = run_py(BACKEND_DIR / "delete_local_folder.py", args=[str(n) for n in repo_names], timeout=timeout)

        installed_count = count_folders(MY_REPOS_DIR)
        new_projects_count = count_folders(NEW_PROJECTS_DIR)
        logger.info(f"Deletion complete, remaining installed: {installed_count}, new projects: {new_projects_count}")
        return jsonify(
            {
                "success": True,
                "output": proc.stdout,
                "error": proc.stderr if proc.returncode != 0 else None,
                "installed_count": installed_count,
                "new_projects_count": new_projects_count,
            }
        )
    except subprocess.TimeoutExpired:
        logger.error("Deletion timed out")
        return jsonify({"error": "Deletion timed out."}), 504
    except Exception as e:
        logger.error(f"Deletion error: {e}")
        return jsonify({"error": str(e)}), 500


def _is_safe_folder_name(name: str) -> bool:
    """
    Reject anything that can escape the intended directories.
    We treat folder_name as a single folder name, not a path.
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


@app.route("/rename", methods=["POST"])
def rename():
    """Rename local project folder in NEW_PROJECTS."""
    data = request.get_json(silent=True) or {}
    old_name = str(data.get("old_name", "")).strip()
    new_name = str(data.get("new_name", "")).strip()

    if not old_name or not new_name:
        return jsonify({"error": "Old name and new name are required"}), 400

    # Validate folder names to prevent path traversal attacks
    if not _is_safe_folder_name(old_name):
        logger.warning(f"Invalid old name for rename: {old_name}")
        return jsonify({"error": "Invalid old name (must be a single folder name, no paths)"}), 400
    if not _is_safe_folder_name(new_name):
        logger.warning(f"Invalid new name for rename: {new_name}")
        return jsonify({"error": "Invalid new name (must be a single folder name, no paths)"}), 400

    try:
        old_path = NEW_PROJECTS_DIR / old_name
        new_path = NEW_PROJECTS_DIR / new_name

        if not old_path.exists():
            logger.warning(f"Folder not found for rename: {old_name}")
            return jsonify({"error": f"Folder '{old_name}' not found"}), 404
        if new_path.exists():
            logger.warning(f"Folder already exists: {new_name}")
            return jsonify({"error": f"Folder '{new_name}' already exists"}), 400

        logger.info(f"Renaming folder: {old_name} -> {new_name}")
        old_path.rename(new_path)
        return jsonify({"success": True, "old_name": old_name, "new_name": new_name})
    except Exception as e:
        logger.error(f"Rename error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/rename-github", methods=["POST"])
def rename_github():
    """Rename GitHub repository and update local folder + YAML."""
    data = request.get_json(silent=True) or {}
    old_name = str(data.get("old_name", "")).strip()
    new_name = str(data.get("new_name", "")).strip()

    if not old_name or not new_name:
        return jsonify({"error": "Old name and new name are required"}), 400

    logger.info(f"Renaming GitHub repo: {old_name} -> {new_name}")
    try:
        proc = run_py(BACKEND_DIR / "rename_github_repo.py", args=[old_name, new_name], timeout=TIMEOUTS["rename"])

        if proc.returncode == 0:
            logger.info(f"GitHub repo renamed successfully: {old_name} -> {new_name}")
            return jsonify(
                {
                    "success": True,
                    "output": proc.stdout,
                    "old_name": old_name,
                    "new_name": new_name,
                }
            )
        logger.error(f"GitHub repo rename failed: {proc.stderr or proc.stdout}")
        return jsonify({"error": proc.stderr or proc.stdout, "output": proc.stdout}), 500

    except subprocess.TimeoutExpired:
        logger.error("Rename timed out")
        return jsonify({"error": "Rename timed out"}), 504
    except Exception as e:
        logger.error(f"Rename error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/open-folder", methods=["POST"])
def open_folder():
    """Open local folder in system file explorer."""
    data = request.get_json(silent=True) or {}
    folder_path = str(data.get("path", "")).strip()

    logger.debug(f"Open folder request: path={folder_path}")

    if not folder_path:
        return jsonify({"error": "Folder path is required"}), 400

    # Convert forward slashes to backslashes for Windows
    folder_path = folder_path.replace("/", "\\")
    
    logger.debug(f"Normalized path: {folder_path}")

    # Verify the folder exists
    if not os.path.exists(folder_path):
        logger.warning(f"Folder not found: {folder_path}")
        return jsonify({"error": f"Folder not found: {folder_path}"}), 404

    # Security check: ensure path is within NEW_PROJECTS or MY_REPOS directory
    try:
        resolved_path = os.path.realpath(folder_path)
        new_projects_real = os.path.realpath(str(NEW_PROJECTS_DIR))
        my_repos_real = os.path.realpath(str(MY_REPOS_DIR))
        
        # Allow paths within NEW_PROJECTS or MY_REPOS
        if not (resolved_path.startswith(new_projects_real) or resolved_path.startswith(my_repos_real)):
            logger.warning(f"Path outside allowed directories: {folder_path}")
            return jsonify({"error": "Invalid folder path"}), 400
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        return jsonify({"error": "Invalid folder path"}), 400

    logger.info(f"Opening folder: {folder_path}")
    try:
        # Open folder in Windows Explorer
        if sys.platform == "win32":
            # Simple explorer open - most reliable
            subprocess.Popen(["explorer", folder_path])
            logger.debug(f"Opened folder in Explorer: {folder_path}")
        else:
            # Fallback for other platforms
            subprocess.run(["xdg-open", folder_path] if sys.platform != "darwin" else ["open", folder_path])

        return jsonify({"success": True, "path": folder_path})
    except Exception as e:
        logger.error(f"Open folder error: {e}")
        return jsonify({"error": str(e)}), 500


# ---- Entrypoint ----

if __name__ == "__main__":
    import signal
    import sys
    import os
    import threading

    # Track the server thread for proper shutdown
    server_thread = None
    shutdown_event = threading.Event()

    def signal_handler(signum, frame):
        """Handle Ctrl+C gracefully."""
        logger.info("\nShutting down gracefully...")
        shutdown_event.set()
        logger.info("Server stopped")
        logger.info("Server shutdown complete")
        # Don't use os._exit() - let Python clean up sockets properly
        sys.exit(0)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Flask with hot reload for all files
    # - Python files: auto-restart server (via watchdog)
    # - HTML/CSS/JS: auto-refresh browser (via flask-hot-reload)
    # - Watchdog: efficient file system monitoring
    # use_reloader=False to avoid daemon thread conflicts on Python 3.14
    try:
        app.run(host="0.0.0.0", port=DEFAULT_PORT, debug=True, use_reloader=False, threaded=True)
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        logger.info("Server stopped")
        logger.info("Server shutdown complete")