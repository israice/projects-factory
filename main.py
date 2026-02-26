#!/usr/bin/env python3
"""
GitHub Projects Manager - Simplified Single-File Version
Run with: python main.py
"""

import json
import os
import re
import subprocess
import sys
from ipaddress import ip_address
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Configuration
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "FRONTEND"
BACKEND_DIR = BASE_DIR / "BACKEND"
MY_REPOS_DIR = BASE_DIR / "MY_REPOS"
NEW_PROJECTS_DIR = BASE_DIR / "NEW_PROJECTS"
YAML_PATH = BACKEND_DIR / "get_all_github_projects.yaml"
SETTINGS_PATH = BASE_DIR / "settings.yaml"

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "Unknown")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
PORT = int(os.getenv("PORT", "5999"))
HOST = os.getenv("HOST", "127.0.0.1")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", f"http://127.0.0.1:{PORT},http://localhost:{PORT}"
    ).split(",")
    if origin.strip()
]

TIMEOUTS = {
    "refresh": 120, "create_project": 120, "install_per_repo": 300,
    "delete_per_repo": 60, "rename": 60, "git_remote": 5,
}
CREATE_PROJECT_REPO_URL = "https://github.com/israice/Create-Project-Folder.git"

app = FastAPI(title="GitHub Projects Manager")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@dataclass
class Project:
    name: str
    url: str
    private: bool
    description: str
    created_at: str
    is_new_project: bool = False

    def as_dict(self):
        return {"name": self.name, "url": self.url, "private": self.private,
                "description": self.description, "created_at": self.created_at,
                "is_new_project": self.is_new_project}


def run_script(script: Path, args=None, timeout=None):
    cmd = [sys.executable, str(script)] + (args or [])
    result = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise Exception((result.stderr or result.stdout or "Failed").strip()[:200])
    return result


def ensure_create_project_script():
    script = MY_REPOS_DIR / "Create-Project-Folder" / "create_new_project.py"
    if script.exists():
        return script

    # Auto-install dependency repo if missing.
    run_script(
        BACKEND_DIR / "install_existing_repo.py",
        [CREATE_PROJECT_REPO_URL],
        timeout=TIMEOUTS["install_per_repo"],
    )

    if not script.exists():
        raise Exception("create_new_project.py was not found after installing Create-Project-Folder")
    return script


def get_installed_urls():
    urls = set()
    if not MY_REPOS_DIR.exists():
        return urls
    for entry in MY_REPOS_DIR.iterdir():
        if entry.is_dir() and (entry / ".git").exists():
            try:
                r = subprocess.run(["git", "-C", str(entry), "remote", "get-url", "origin"],
                                   capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    url = (r.stdout or "").strip().removesuffix(".git").rstrip("/")
                    urls.add(url)
            except:
                pass
    return urls


def get_new_projects():
    projects = []
    if not NEW_PROJECTS_DIR.exists():
        return projects
    for entry in NEW_PROJECTS_DIR.iterdir():
        if entry.is_dir():
            try:
                ts = entry.stat().st_ctime
                created = datetime.fromtimestamp(ts).isoformat() + "Z"
            except:
                created = ""
            projects.append(Project(entry.name, str(entry).replace("\\", "/"),
                                    False, "Local project folder", created, True).as_dict())
    return projects


def load_yaml_repos():
    if not YAML_PATH.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
        return [r for r in (data.get("repositories", []) or []) if isinstance(r, dict)]
    except:
        return []


def get_avatar():
    if not GITHUB_USERNAME:
        return ""
    try:
        import requests
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        r = requests.get(f"https://api.github.com/users/{GITHUB_USERNAME}",
                        headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json().get("avatar_url", "")
    except:
        pass
    return ""


def count_folders(path: Path):
    return sum(1 for p in path.iterdir() if p.is_dir()) if path.exists() else 0


def safe_name(name):
    if not name or name.strip() != name:
        return False
    p = Path(name)
    if p.is_absolute() or ".." in p.parts or "." in p.parts or len(p.parts) != 1:
        return False
    if sys.platform == "win32" and ":" in name:
        return False
    return True


def repo_name_from_url(repo_url: str):
    u = str(repo_url or "").strip().rstrip("/")
    if not u:
        return ""
    m = re.search(r":([^/]+)/([^/]+)$", u)
    name = m.group(2) if m else u.split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name.strip()


def _is_loopback_host(host: str):
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def require_write_access(request: Request):
    client_host = request.client.host if request.client else ""
    if not _is_loopback_host(client_host):
        raise HTTPException(403, "Write access is limited to local requests")


def update_yaml_rename(old, new):
    if not YAML_PATH.exists():
        return
    try:
        import yaml
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
        for repo in (data.get("repositories", []) or []):
            if isinstance(repo, dict) and repo.get("name") == old:
                repo["name"] = new
                if "url" in repo and isinstance(repo["url"], str):
                    repo["url"] = repo["url"].rstrip("/").removesuffix(old) + new
        YAML_PATH.write_text(yaml.safe_dump(data, allow_unicode=True,
                                            sort_keys=False, default_flow_style=False), encoding="utf-8")
    except:
        pass


def update_yaml_description(name, description):
    if not YAML_PATH.exists():
        return
    try:
        import yaml
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
        for repo in (data.get("repositories", []) or []):
            if isinstance(repo, dict) and repo.get("name") == name:
                repo["description"] = description
                break
        YAML_PATH.write_text(yaml.safe_dump(data, allow_unicode=True,
                                            sort_keys=False, default_flow_style=False), encoding="utf-8")
    except:
        pass


def remove_repo_from_yaml(name):
    if not YAML_PATH.exists():
        return
    try:
        import yaml
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
        repos = [r for r in (data.get("repositories", []) or [])
                 if not (isinstance(r, dict) and r.get("name") == name)]
        data["repositories"] = repos
        YAML_PATH.write_text(yaml.safe_dump(data, allow_unicode=True,
                                            sort_keys=False, default_flow_style=False), encoding="utf-8")
    except:
        pass


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(str(FRONTEND_DIR / "favicon.svg"), media_type="image/svg+xml")


@app.get("/api/config")
async def config():
    installed_urls = list(get_installed_urls())
    return {"username": GITHUB_USERNAME, "avatar_url": get_avatar(),
            "installed_count": len(installed_urls),
            "installed_urls": installed_urls}


@app.get("/api/repos")
async def repos():
    yaml_repos = load_yaml_repos()
    sorted_repos = sorted(yaml_repos, key=lambda r: (r.get("name") != GITHUB_USERNAME,
                                                      str(r.get("name", "")).lower()))
    return {"repos": sorted_repos + get_new_projects(), "count": len(sorted_repos)}


@app.post("/api/refresh")
async def refresh(request: Request):
    require_write_access(request)
    try:
        run_script(BACKEND_DIR / "get_all_github_projects.py", timeout=TIMEOUTS["refresh"])
        return {"success": True, "message": "✅ Repositories refreshed"}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/create-project")
async def create_project(request: Request):
    require_write_access(request)
    try:
        script = ensure_create_project_script()
        result = run_script(script, timeout=TIMEOUTS["create_project"])
        output = (result.stdout or "").strip()
        folder = ""
        try:
            data = json.loads(output)
            if isinstance(data, dict) and data.get("success"):
                folder = data.get("folder_name", "")
        except:
            if 'Project "' in output and '" created' in output:
                folder = output.split('Project "')[1].split('" created')[0]
        return {"success": True, "message": f'Project "{folder}" created' if folder else "Project created",
                "folder_name": folder}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/install")
async def install(payload: dict, request: Request):
    require_write_access(request)
    urls = payload.get("repos", [])
    if not urls:
        raise HTTPException(400, "No repositories selected")
    try:
        run_script(BACKEND_DIR / "install_existing_repo.py", [str(u) for u in urls],
                   timeout=TIMEOUTS["install_per_repo"] * len(urls))
        return {"success": True, "installed_count": count_folders(MY_REPOS_DIR)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/delete")
async def delete(payload: dict, request: Request):
    require_write_access(request)
    names = payload.get("repos", [])
    if not names:
        raise HTTPException(400, "No repositories selected")
    try:
        run_script(BACKEND_DIR / "delete_local_folder.py", [str(n) for n in names],
                   timeout=TIMEOUTS["delete_per_repo"] * len(names))
        return {"success": True, "installed_count": count_folders(MY_REPOS_DIR),
                "new_projects_count": count_folders(NEW_PROJECTS_DIR)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/rename")
async def rename_local(payload: dict, request: Request):
    require_write_access(request)
    old, new = payload.get("old_name", "").strip(), payload.get("new_name", "").strip()
    if not old or not new or not safe_name(old) or not safe_name(new):
        raise HTTPException(400, "Invalid names")
    old_path, new_path = NEW_PROJECTS_DIR / old, NEW_PROJECTS_DIR / new
    if not old_path.exists():
        raise HTTPException(404, f"Folder '{old}' not found")
    if new_path.exists():
        raise HTTPException(400, f"Folder '{new}' already exists")
    old_path.rename(new_path)
    update_yaml_rename(old, new)
    return {"success": True, "old_name": old, "new_name": new}


@app.post("/api/rename-github")
async def rename_github(payload: dict, request: Request):
    require_write_access(request)
    old, new = payload.get("old_name", "").strip(), payload.get("new_name", "").strip()
    if not old or not new:
        raise HTTPException(400, "Invalid names")
    try:
        result = run_script(BACKEND_DIR / "rename_github_repo.py", [old, new],
                           timeout=TIMEOUTS["rename"])
        return {"success": True, "old_name": old, "new_name": new, "output": result.stdout}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/delete-github")
async def delete_github(payload: dict, request: Request):
    require_write_access(request)
    name = payload.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Invalid repository name")
    if not GITHUB_TOKEN:
        raise HTTPException(500, "GITHUB_TOKEN is not configured")

    try:
        import requests
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{name}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "projects-factory/github-delete",
        }
        r = requests.delete(api_url, headers=headers, timeout=30)
        if r.status_code not in (204,):
            detail = ""
            try:
                body = r.json()
                detail = body.get("message", "")
            except:
                detail = r.text
            raise HTTPException(500, f"GitHub API error {r.status_code}: {detail[:200]}")

        remove_repo_from_yaml(name)
        return {"success": True, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/update-description")
async def update_description(payload: dict, request: Request):
    require_write_access(request)
    name = payload.get("name", "").strip()
    description = str(payload.get("description", ""))
    if not name:
        raise HTTPException(400, "Invalid repository name")
    if not GITHUB_TOKEN:
        raise HTTPException(500, "GITHUB_TOKEN is not configured")

    try:
        import requests
        api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{name}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "projects-factory/description-update",
        }
        r = requests.patch(api_url, json={"description": description}, headers=headers, timeout=30)
        if r.status_code != 200:
            detail = ""
            try:
                body = r.json()
                detail = body.get("message", "")
            except:
                detail = r.text
            raise HTTPException(500, f"GitHub API error {r.status_code}: {detail[:200]}")

        update_yaml_description(name, description)
        return {"success": True, "name": name, "description": description}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/open-folder")
async def open_folder(payload: dict, request: Request):
    require_write_access(request)
    raw_path = str(payload.get("path", "")).strip()
    if not raw_path:
        raise HTTPException(404, "Folder not found")

    resolved = None

    direct = Path(raw_path).expanduser()
    if direct.exists() and direct.is_dir():
        resolved = direct.resolve()
    else:
        guessed_name = repo_name_from_url(raw_path)
        if not guessed_name:
            guessed_name = Path(raw_path).name.strip()
        if guessed_name:
            guessed = (MY_REPOS_DIR / guessed_name).resolve()
            if guessed.exists() and guessed.is_dir():
                resolved = guessed
            else:
                guessed = (NEW_PROJECTS_DIR / guessed_name).resolve()
                if guessed.exists() and guessed.is_dir():
                    resolved = guessed

    if not resolved:
        raise HTTPException(404, "Folder not found")

    allowed_roots = (NEW_PROJECTS_DIR.resolve(), MY_REPOS_DIR.resolve())
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise HTTPException(400, "Invalid path")

    try:
        run_script(BACKEND_DIR / "open_in_vscode.py", [str(resolved)], timeout=30)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"success": True, "path": str(resolved)}


if __name__ == "__main__":
    import uvicorn
    print(f"GitHub Projects Manager on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, reload=False)
