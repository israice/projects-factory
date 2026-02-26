#!/usr/bin/env python3
"""
FastAPI backend for GitHub Projects Manager.

Provides REST API endpoints for:
- Getting repositories list (GitHub + local projects)
- Installing/deleting/renaming repositories
- Opening folders
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
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress noisy logs
logging.getLogger('urllib3').setLevel(logging.WARNING)

try:
    import requests
except Exception:
    requests = None  # type: ignore[assignment]


# ---- Configuration ----

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "FRONTEND"
TEMPLATES_DIR = BASE_DIR / "TEMPLATES"
BACKEND_DIR = BASE_DIR / "BACKEND"
MY_REPOS_DIR = BASE_DIR / "MY_REPOS"
NEW_PROJECTS_DIR = BASE_DIR / "NEW_PROJECTS"
YAML_PATH = BACKEND_DIR / "get_all_github_projects.yaml"
SETTINGS_PATH = BASE_DIR / "settings.yaml"

# Timeouts
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
        return DEFAULT_TIMEOUTS

    try:
        data = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
        timeouts = data.get("timeouts", {})
        if not isinstance(timeouts, dict):
            return DEFAULT_TIMEOUTS
        return {**DEFAULT_TIMEOUTS, **timeouts}
    except Exception:
        return DEFAULT_TIMEOUTS


TIMEOUTS = load_timeouts()

# FastAPI app
app = FastAPI(title="GitHub Projects Manager API", version="2.0.0")

# Templates for SSR (server-side rendering)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Helper Functions ----

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
    """Run a Python script using the current interpreter."""
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd += args

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
        )
    except subprocess.TimeoutExpired:
        logger.error(f"Script {script_path} timed out after {timeout}s")
        raise


def get_installed_repo_urls(my_repos_dir: Path) -> set[str]:
    """Get set of normalized Git repo origin URLs from installed repositories."""
    installed: set[str] = set()
    if not my_repos_dir.exists():
        return installed

    for entry in my_repos_dir.iterdir():
        if not entry.is_dir() or not (entry / ".git").exists():
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(entry), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=TIMEOUTS["git_remote"],
            )
            if result.returncode == 0:
                remote_url = (result.stdout or "").strip()
                if remote_url.endswith(".git"):
                    remote_url = remote_url[:-4]
                installed.add(remote_url.rstrip("/"))
        except (subprocess.TimeoutExpired, Exception):
            pass

    return installed


def get_new_projects(new_projects_dir: Path) -> list[dict[str, Any]]:
    """Get list of new projects from NEW_PROJECTS directory."""
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
    """Load repositories from YAML file."""
    if not yaml_path.exists():
        return []

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        repos = data.get("repositories", [])
        if not isinstance(repos, list):
            return []
        return [r for r in repos if isinstance(r, dict)]
    except Exception:
        return []


def fetch_avatar_url(username: str, token: str) -> str:
    """Fetch user avatar URL from GitHub API."""
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
    """Count subdirectories in a path."""
    if not dir_path.exists():
        return 0
    try:
        return sum(1 for p in dir_path.iterdir() if p.is_dir())
    except Exception:
        return 0


def _is_safe_folder_name(name: str) -> bool:
    """Validate folder name to prevent path traversal attacks."""
    if not name or name.strip() != name:
        return False
    p = Path(name)
    if p.is_absolute():
        return False
    if any(part in ("..", ".") for part in p.parts):
        return False
    if len(p.parts) != 1:
        return False
    if sys.platform == "win32" and ":" in name:
        return False
    return True


def _update_yaml_rename(yaml_path: Path, old_name: str, new_name: str) -> bool:
    """Update YAML file when renaming a project."""
    if not yaml_path.exists():
        return False

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        repos = data.get("repositories", [])
        if not isinstance(repos, list):
            return False

        for repo in repos:
            if isinstance(repo, dict) and repo.get("name") == old_name:
                repo["name"] = new_name
                if "url" in repo and isinstance(repo["url"], str):
                    repo["url"] = repo["url"].rstrip("/")
                    if repo["url"].endswith(old_name):
                        repo["url"] = repo["url"][: -len(old_name)] + new_name
                break

        yaml_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


# ---- API Endpoints ----

@app.get("/api/config")
async def get_config():
    """Get application configuration."""
    load_dotenv()
    username = os.getenv("GITHUB_USERNAME", "Unknown")
    token = os.getenv("GITHUB_TOKEN", "")
    
    avatar_url = fetch_avatar_url(username, token)
    installed_urls = get_installed_repo_urls(MY_REPOS_DIR)
    
    return {
        "username": username,
        "avatar_url": avatar_url,
        "installed_count": len(installed_urls),
    }


@app.get("/api/repos")
async def get_repos():
    """Get all repositories (GitHub + local projects)."""
    repos = load_repos_from_yaml(YAML_PATH)
    repos_sorted = sorted(
        repos,
        key=lambda r: (r.get("name") != os.getenv("GITHUB_USERNAME", ""), str(r.get("name", "")).lower()),
    )
    
    new_projects = get_new_projects(NEW_PROJECTS_DIR)
    all_projects = repos_sorted + new_projects
    
    return {"repos": all_projects, "count": len(repos_sorted)}


@app.post("/api/refresh")
async def refresh_repos():
    """Refresh repositories list by running get_all_github_projects.py."""
    logger.info("Starting repositories refresh")
    try:
        proc = run_py(BACKEND_DIR / "get_all_github_projects.py", timeout=TIMEOUTS["refresh"])
        if proc.returncode != 0:
            error_msg = (proc.stderr or proc.stdout or "Refresh failed").strip()
            logger.error(f"Refresh failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Refresh failed: {error_msg[:200]}")
        
        logger.info("Repositories refreshed successfully")
        return {"success": True, "message": "✅ Repositories refreshed successfully"}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Refresh timed out")
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/create-project")
async def create_project():
    """Create new project folder."""
    logger.info("Starting new project creation")
    try:
        proc = run_py(
            MY_REPOS_DIR / "Create-Project-Folder" / "create_new_project.py",
            timeout=TIMEOUTS["create_project"],
        )
        
        if proc.returncode != 0:
            error_msg = (proc.stderr or proc.stdout or "Create project failed").strip()
            logger.error(f"Create project failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Create project failed: {error_msg[:200]}")

        output = (proc.stdout or "").strip()
        folder_name = ""
        
        try:
            result = json.loads(output)
            if isinstance(result, dict) and result.get("success"):
                folder_name = result.get("folder_name", "")
        except json.JSONDecodeError:
            if 'Project "' in output and '" created' in output:
                start = output.find('Project "') + len('Project "')
                end = output.find('" created')
                folder_name = output[start:end]

        message = f'Project "{folder_name}" created successfully' if folder_name else "Project created successfully"
        return {"success": True, "message": message, "folder_name": folder_name}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Create project timed out")
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/install")
async def install_repos(payload: dict[str, Any]):
    """Install selected repositories."""
    repo_urls = payload.get("repos", [])
    if not isinstance(repo_urls, list) or not repo_urls:
        raise HTTPException(status_code=400, detail="No repositories selected")

    logger.info(f"Installing {len(repo_urls)} repositories")
    try:
        timeout = TIMEOUTS["install_per_repo"] * len(repo_urls)
        proc = run_py(
            BACKEND_DIR / "install_existing_repo.py",
            args=[str(u) for u in repo_urls],
            timeout=timeout,
        )

        installed_count = count_folders(MY_REPOS_DIR)
        return {
            "success": True,
            "output": proc.stdout,
            "error": proc.stderr if proc.returncode != 0 else None,
            "installed_count": installed_count,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Installation timed out")
    except Exception as e:
        logger.error(f"Installation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/delete")
async def delete_repos(payload: dict[str, Any]):
    """Delete selected repositories."""
    repo_names = payload.get("repos", [])
    if not isinstance(repo_names, list) or not repo_names:
        raise HTTPException(status_code=400, detail="No repositories selected")

    logger.info(f"Deleting {len(repo_names)} repositories")
    try:
        timeout = TIMEOUTS["delete_per_repo"] * len(repo_names)
        proc = run_py(
            BACKEND_DIR / "delete_local_folder.py",
            args=[str(n) for n in repo_names],
            timeout=timeout,
        )

        installed_count = count_folders(MY_REPOS_DIR)
        new_projects_count = count_folders(NEW_PROJECTS_DIR)
        return {
            "success": True,
            "output": proc.stdout,
            "error": proc.stderr if proc.returncode != 0 else None,
            "installed_count": installed_count,
            "new_projects_count": new_projects_count,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Deletion timed out")
    except Exception as e:
        logger.error(f"Deletion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rename")
async def rename_local(payload: dict[str, str]):
    """Rename local project folder in NEW_PROJECTS."""
    old_name = payload.get("old_name", "").strip()
    new_name = payload.get("new_name", "").strip()

    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Old name and new name are required")

    if not _is_safe_folder_name(old_name) or not _is_safe_folder_name(new_name):
        raise HTTPException(status_code=400, detail="Invalid folder name")

    try:
        old_path = NEW_PROJECTS_DIR / old_name
        new_path = NEW_PROJECTS_DIR / new_name

        if not old_path.exists():
            raise HTTPException(status_code=404, detail=f"Folder '{old_name}' not found")
        if new_path.exists():
            raise HTTPException(status_code=400, detail=f"Folder '{new_name}' already exists")

        logger.info(f"Renaming folder: {old_name} -> {new_name}")
        old_path.rename(new_path)
        _update_yaml_rename(YAML_PATH, old_name, new_name)

        return {"success": True, "old_name": old_name, "new_name": new_name}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rename error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/rename-github")
async def rename_github_repo(payload: dict[str, str]):
    """Rename GitHub repository."""
    old_name = payload.get("old_name", "").strip()
    new_name = payload.get("new_name", "").strip()

    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Old name and new name are required")

    logger.info(f"Renaming GitHub repo: {old_name} -> {new_name}")
    try:
        proc = run_py(
            BACKEND_DIR / "rename_github_repo.py",
            args=[old_name, new_name],
            timeout=TIMEOUTS["rename"],
        )

        if proc.returncode == 0:
            logger.info(f"GitHub repo renamed successfully: {old_name} -> {new_name}")
            return {"success": True, "output": proc.stdout, "old_name": old_name, "new_name": new_name}
        
        logger.error(f"GitHub repo rename failed: {proc.stderr or proc.stdout}")
        raise HTTPException(status_code=500, detail=proc.stderr or proc.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Rename timed out")
    except Exception as e:
        logger.error(f"Rename error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/open-folder")
async def open_folder(payload: dict[str, str]):
    """Open local folder in system file explorer."""
    folder_path = payload.get("path", "").strip()

    if not folder_path:
        raise HTTPException(status_code=400, detail="Folder path is required")

    folder_path = folder_path.replace("/", "\\")

    if not os.path.exists(folder_path):
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")

    try:
        resolved_path = os.path.realpath(folder_path)
        new_projects_real = os.path.realpath(str(NEW_PROJECTS_DIR))
        my_repos_real = os.path.realpath(str(MY_REPOS_DIR))

        if not (resolved_path.startswith(new_projects_real) or resolved_path.startswith(my_repos_real)):
            raise HTTPException(status_code=400, detail="Invalid folder path")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Path validation error: {e}")
        raise HTTPException(status_code=400, detail="Invalid folder path")

    logger.info(f"Opening folder: {folder_path}")
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder_path])
        else:
            subprocess.run(["xdg-open", folder_path] if sys.platform != "darwin" else ["open", folder_path])
        return {"success": True, "path": folder_path}
    except Exception as e:
        logger.error(f"Open folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---- Static Files & Frontend ----

# Mount static files
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")


def _prepare_page_data():
    """Prepare data for server-side rendered page."""
    import json as json_module
    
    load_dotenv()
    username = os.getenv("GITHUB_USERNAME", "Unknown")
    token = os.getenv("GITHUB_TOKEN", "")

    avatar_url = fetch_avatar_url(username, token)
    installed_urls = get_installed_repo_urls(MY_REPOS_DIR)
    repos = load_repos_from_yaml(YAML_PATH)
    repos_sorted = sorted(
        repos,
        key=lambda r: (r.get("name") != username, str(r.get("name", "")).lower()),
    )
    new_projects = get_new_projects(NEW_PROJECTS_DIR)
    all_projects = repos_sorted + new_projects

    return {
        "username": username,
        "avatar_url": avatar_url,
        "installed_count": len(installed_urls),
        "repos_count": len(repos_sorted),
        "repos": all_projects,
        "installed_urls": list(installed_urls),
        "repos_json": json_module.dumps(all_projects, ensure_ascii=False),
        "installed_urls_json": json_module.dumps(list(installed_urls), ensure_ascii=False),
    }


@app.get("/test", response_class=HTMLResponse)
async def serve_test(request: Request):
    """Test endpoint with minimal template."""
    page_data = _prepare_page_data()
    return templates.TemplateResponse("test.html", {
        "request": request,
        "username": page_data["username"],
        "repos_count": page_data["repos_count"],
        "repos": page_data["repos"],
    })


@app.get("/", response_class=HTMLResponse)
async def serve_frontend(request: Request):
    """Serve the main frontend application with SSR for instant load."""
    import traceback
    
    try:
        page_data = _prepare_page_data()
        
        # Remove complex data that might cause serialization issues
        template_data = {
            "request": request,
            "username": page_data["username"],
            "avatar_url": page_data["avatar_url"],
            "installed_count": page_data["installed_count"],
            "repos_count": page_data["repos_count"],
            "repos_json": page_data["repos_json"],
            "installed_urls_json": page_data["installed_urls_json"],
            "repos": page_data["repos"],
            "installed_urls": page_data["installed_urls"],
        }
        
        return templates.TemplateResponse("index.html", template_data)
    except Exception as e:
        # Log full traceback for debugging
        print("ERROR in serve_frontend:")
        print(traceback.format_exc())
        raise


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(str(FRONTEND_DIR / "favicon.ico"), media_type="image/x-icon")


# ---- Entrypoint ----

if __name__ == "__main__":
    import uvicorn
    
    PORT = int(os.getenv("PORT", "5999"))
    logger.info(f"Starting API server on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)
