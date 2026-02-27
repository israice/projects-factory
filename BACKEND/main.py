#!/usr/bin/env python3
"""
GitHub Projects Manager - Simplified Single-File Version
Run with: python run.py
"""

import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import warnings
import logging
import time
from ipaddress import ip_address
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

# Disable .pyc/__pycache__ creation for this process and child Python runs.
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from BACKEND.api_models import (
    AddToGithubPayload,
    InstallPayload,
    DeletePayload,
    RenamePayload,
    DeleteGithubPayload,
    UpdateDescriptionPayload,
    OpenFolderPayload,
    PushPayload,
)

load_dotenv()
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("projects_factory")

warnings.filterwarnings(
    "ignore",
    message=r"urllib3 .* doesn't match a supported version!",
    module=r"requests(\..*)?$",
)

# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
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

def load_function_settings():
    if not SETTINGS_PATH.exists():
        raise RuntimeError(f"Missing required settings file: {SETTINGS_PATH}")

    try:
        import yaml
        raw = yaml.safe_load(SETTINGS_PATH.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise RuntimeError(f"Failed to read settings.yaml: {exc}") from exc

    if not isinstance(raw, dict):
        raise RuntimeError("settings.yaml must contain a top-level mapping")

    def require_mapping(container: dict, key: str):
        value = container.get(key)
        if not isinstance(value, dict):
            raise RuntimeError(f"settings.yaml missing required mapping: {key}")
        return value

    def require_positive_int(container: dict, key: str, path: str):
        value = container.get(key)
        if value is None:
            raise RuntimeError(f"settings.yaml missing required key: {path}")
        try:
            num = int(value)
        except Exception as exc:
            raise RuntimeError(f"settings.yaml key '{path}' must be integer") from exc
        if num < 1:
            raise RuntimeError(f"settings.yaml key '{path}' must be >= 1")
        return num

    def require_string(container: dict, key: str, path: str):
        value = container.get(key)
        if value is None:
            raise RuntimeError(f"settings.yaml missing required key: {path}")
        text = str(value).strip()
        if not text:
            raise RuntimeError(f"settings.yaml key '{path}' must be non-empty string")
        return text

    timeouts_src = require_mapping(raw, "timeouts")
    timeouts = {
        "refresh": require_positive_int(timeouts_src, "refresh", "timeouts.refresh"),
        "create_project": require_positive_int(timeouts_src, "create_project", "timeouts.create_project"),
        "install_per_repo": require_positive_int(timeouts_src, "install_per_repo", "timeouts.install_per_repo"),
        "delete_per_repo": require_positive_int(timeouts_src, "delete_per_repo", "timeouts.delete_per_repo"),
        "rename": require_positive_int(timeouts_src, "rename", "timeouts.rename"),
        "git_remote": require_positive_int(timeouts_src, "git_remote", "timeouts.git_remote"),
        "git_push": require_positive_int(timeouts_src, "git_push", "timeouts.git_push"),
    }

    cache_src = require_mapping(raw, "cache")
    cache = {
        "git_state_ttl_sec": require_positive_int(cache_src, "git_state_ttl_sec", "cache.git_state_ttl_sec"),
    }

    python_src = require_mapping(raw, "python")
    if "disable_bytecode" not in python_src:
        raise RuntimeError("settings.yaml missing required key: python.disable_bytecode")
    disable_bytecode = python_src["disable_bytecode"]
    if isinstance(disable_bytecode, str):
        disable_bytecode = disable_bytecode.strip().lower() in ("1", "true", "yes", "on")
    else:
        disable_bytecode = bool(disable_bytecode)
    if not disable_bytecode:
        raise RuntimeError("settings.yaml requires python.disable_bytecode: true")

    ui_src = require_mapping(raw, "ui")
    default_push_message = require_string(ui_src, "default_push_message", "ui.default_push_message")
    create_project_repo_url = require_string(raw, "create_project_repo_url", "create_project_repo_url")

    return {
        "timeouts": timeouts,
        "create_project_repo_url": create_project_repo_url,
        "cache": cache,
        "python": {"disable_bytecode": disable_bytecode},
        "ui": {"default_push_message": default_push_message},
    }


FUNCTION_SETTINGS = load_function_settings()
TIMEOUTS = FUNCTION_SETTINGS["timeouts"]
CREATE_PROJECT_REPO_URL = FUNCTION_SETTINGS["create_project_repo_url"]
GIT_STATE_TTL_SEC = FUNCTION_SETTINGS["cache"]["git_state_ttl_sec"]
DISABLE_BYTECODE = FUNCTION_SETTINGS["python"]["disable_bytecode"]
DEFAULT_PUSH_MESSAGE = FUNCTION_SETTINGS["ui"]["default_push_message"]

app = FastAPI(title="GitHub Projects Manager")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.middleware("http")
async def force_static_200(request: Request, call_next):
    if request.url.path.startswith("/static/"):
        # Remove conditional request headers so static responses are sent as 200.
        headers = request.scope.get("headers") or []
        request.scope["headers"] = [
            (k, v) for (k, v) in headers
            if k.lower() not in (b"if-none-match", b"if-modified-since")
        ]
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store"
    return response


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


GIT_STATE_CACHE = {"by_path": {}, "by_remote": {}, "expires_at": 0.0}


def invalidate_runtime_caches():
    GIT_STATE_CACHE["expires_at"] = 0.0


def run_script(script: Path, args=None, timeout=None):
    cmd = [sys.executable, str(script)] + (args or [])
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Guard child Python processes from broken interpreter env overrides.
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    result = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', errors='replace', env=env)
    if result.returncode != 0:
        raise Exception((result.stderr or result.stdout or "Failed").strip()[:200])
    return result


def run_command(cmd, cwd=None, timeout=None):
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise Exception((result.stderr or result.stdout or "Failed").strip()[:400])
    return result


def is_non_fast_forward_error(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "non-fast-forward",
        "[rejected]",
        "fetch first",
        "tip of your current branch is behind",
        "failed to push some refs",
    )
    return any(marker in text for marker in markers)


def get_last_version_line(repo_root: Path) -> str:
    version_file = repo_root / "VERSION.md"
    if not version_file.exists():
        return ""
    try:
        lines = version_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    for line in reversed(lines):
        text = line.strip()
        if text:
            return text
    return ""


def is_image_file(path: Path) -> bool:
    if not path.is_file():
        return False
    media_type, _ = mimetypes.guess_type(str(path))
    if media_type and media_type.startswith("image/"):
        return True
    return path.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico")


def get_project_screenshots_dir(project_root: Path) -> Path:
    return project_root / "TOOLS" / "SCREENSHOTS"


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
    candidates = []
    if MY_REPOS_DIR.exists():
        candidates.extend([entry for entry in MY_REPOS_DIR.iterdir() if entry.is_dir()])
    if (BASE_DIR / ".git").exists():
        candidates.append(BASE_DIR)

    for entry in candidates:
        try:
            r = subprocess.run(["git", "-C", str(entry), "remote", "get-url", "origin"],
                               capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                url = (r.stdout or "").strip().removesuffix(".git").rstrip("/")
                urls.add(url)
        except Exception as exc:
            logger.debug("Skipping remote url for %s: %s", entry, exc)
    return urls


def get_new_projects(states_by_path=None):
    projects = []
    if not NEW_PROJECTS_DIR.exists():
        return projects
    for entry in NEW_PROJECTS_DIR.iterdir():
        if entry.is_dir():
            # If folder is already connected to GitHub, do not show it as local-only.
            try:
                resolved_key = str(entry.resolve())
                if states_by_path and resolved_key in states_by_path:
                    if states_by_path[resolved_key].get("is_github_remote"):
                        continue
                elif (entry / ".git").exists():
                    r = subprocess.run(["git", "-C", str(entry), "remote", "get-url", "origin"],
                                       capture_output=True, text=True, timeout=5)
                    origin = (r.stdout or "").strip().lower()
                    if r.returncode == 0 and "github.com" in origin:
                        continue
            except Exception as exc:
                logger.debug("Cannot inspect local project remote %s: %s", entry, exc)
            try:
                ts = entry.stat().st_ctime
                created = datetime.fromtimestamp(ts).isoformat() + "Z"
            except Exception as exc:
                logger.debug("Cannot read creation time for %s: %s", entry, exc)
                created = ""
            projects.append(Project(entry.name, str(entry).replace("\\", "/"),
                                    False, "", created, True).as_dict())
    return projects


def normalize_repo_url(url: str):
    return str(url or "").strip().rstrip("/").removesuffix(".git").lower()


def get_local_git_states(force_refresh=False):
    now = time.time()
    if (not force_refresh) and GIT_STATE_CACHE["expires_at"] > now:
        return GIT_STATE_CACHE["by_path"], GIT_STATE_CACHE["by_remote"]

    states_by_path = {}
    states_by_remote = {}
    candidates = []
    for root in (MY_REPOS_DIR, NEW_PROJECTS_DIR):
        if not root.exists():
            continue
        candidates.extend([entry for entry in root.iterdir() if entry.is_dir() and (entry / ".git").exists()])
    if (BASE_DIR / ".git").exists():
        candidates.append(BASE_DIR)

    for entry in candidates:
        resolved = str(entry.resolve())

        has_uncommitted = False
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(entry),
                capture_output=True,
                text=True,
                timeout=TIMEOUTS["git_remote"],
                encoding="utf-8",
                errors="replace",
            )
            if status.returncode == 0 and (status.stdout or "").strip():
                has_uncommitted = True
        except Exception as exc:
            logger.debug("git status failed for %s: %s", entry, exc)

        has_origin = False
        remote_norm = ""
        remote_url = ""
        try:
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=str(entry),
                capture_output=True,
                text=True,
                timeout=TIMEOUTS["git_remote"],
                encoding="utf-8",
                errors="replace",
            )
            remote_url = (remote.stdout or "").strip()
            if remote.returncode == 0 and remote_url:
                has_origin = True
                remote_norm = normalize_repo_url(remote_url)
        except Exception as exc:
            logger.debug("git remote get-url failed for %s: %s", entry, exc)

        state = {
            "has_uncommitted": has_uncommitted,
            "has_origin": has_origin,
            "is_github_remote": ("github.com" in remote_url.lower()) if has_origin else False,
            "can_push": has_uncommitted and has_origin,
        }
        states_by_path[resolved] = state
        if remote_norm:
            states_by_remote[remote_norm] = state

    GIT_STATE_CACHE["by_path"] = states_by_path
    GIT_STATE_CACHE["by_remote"] = states_by_remote
    GIT_STATE_CACHE["expires_at"] = now + GIT_STATE_TTL_SEC
    return states_by_path, states_by_remote


def load_yaml_repos():
    if not YAML_PATH.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8")) or {}
        return [r for r in (data.get("repositories", []) or []) if isinstance(r, dict)]
    except Exception as exc:
        logger.warning("Failed to load YAML repos: %s", exc)
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
    except Exception as exc:
        logger.debug("Failed to load avatar: %s", exc)
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


PROJECTS_FACTORY_REPO_URL = "https://github.com/israice/projects-factory"
PROJECTS_FACTORY_REPO_NAME = repo_name_from_url(PROJECTS_FACTORY_REPO_URL).lower()


def resolve_project_path(raw_path: str):
    raw = str(raw_path or "").strip()
    if not raw:
        return None

    resolved = None
    direct = Path(raw).expanduser()
    if direct.exists() and direct.is_dir():
        resolved = direct.resolve()
    else:
        normalized_raw = normalize_repo_url(raw)
        # Special-case: this repository lives in BASE_DIR (one level above MY_REPOS/*).
        if (BASE_DIR / ".git").exists() and (
            normalized_raw == normalize_repo_url(PROJECTS_FACTORY_REPO_URL)
            or repo_name_from_url(raw).strip().lower() == PROJECTS_FACTORY_REPO_NAME
        ):
            resolved = BASE_DIR.resolve()
        else:
            guessed_name = repo_name_from_url(raw)
            if not guessed_name:
                guessed_name = Path(raw).name.strip()
            if guessed_name:
                guessed = (MY_REPOS_DIR / guessed_name).resolve()
                if guessed.exists() and guessed.is_dir():
                    resolved = guessed
                else:
                    guessed = (NEW_PROJECTS_DIR / guessed_name).resolve()
                    if guessed.exists() and guessed.is_dir():
                        resolved = guessed
                    else:
                        # Fallback to current workspace repo only if no local repo folder matched.
                        if BASE_DIR.name == guessed_name and (BASE_DIR / ".git").exists():
                            resolved = BASE_DIR.resolve()

    if not resolved:
        return None

    allowed_roots = (NEW_PROJECTS_DIR.resolve(), MY_REPOS_DIR.resolve(), BASE_DIR.resolve())
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        return None
    return resolved


def _list_windows_explorer_handles():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    handles = []
    class_names = {"CabinetWClass", "ExplorerWClass"}
    buffer_size = 256

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        class_buf = ctypes.create_unicode_buffer(buffer_size)
        user32.GetClassNameW(hwnd, class_buf, buffer_size)
        if class_buf.value in class_names:
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc, 0)
    return handles


def _force_foreground_window(hwnd: int):
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
        # Toggle TOPMOST to move explorer above other windows, then restore normal z-order.
        user32.SetWindowPos(hwnd, hwnd_topmost, 0, 0, 0, 0, swp_nosize | swp_nomove | swp_showwindow)
        user32.SetWindowPos(hwnd, hwnd_notopmost, 0, 0, 0, 0, swp_nosize | swp_nomove | swp_showwindow)
        user32.SetForegroundWindow(hwnd)
        user32.SetActiveWindow(hwnd)
        user32.SetFocus(hwnd)
    finally:
        if attached_target:
            user32.AttachThreadInput(target_tid, cur_tid, False)
        if attached_fg:
            user32.AttachThreadInput(fg_tid, cur_tid, False)


def open_folder_in_explorer(path: Path):
    if os.name == "nt":
        import ctypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        before = set(_list_windows_explorer_handles())
        subprocess.Popen(
            ["cmd", "/c", "start", "", "explorer", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        selected = None
        deadline = time.time() + 4.0
        while time.time() < deadline:
            time.sleep(0.05)
            current = _list_windows_explorer_handles()
            new_handles = [hwnd for hwnd in current if hwnd not in before]
            if new_handles:
                selected = new_handles[-1]
                break
            if current:
                selected = current[-1]

        if not selected:
            selected = int(user32.GetForegroundWindow() or 0) or None
        if selected:
            _force_foreground_window(selected)
        return

    if sys.platform == "darwin":
        run_command(["open", str(path)], timeout=30)
        return

    run_command(["xdg-open", str(path)], timeout=30)


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
    except Exception as exc:
        logger.warning("Failed to update YAML rename (%s -> %s): %s", old, new, exc)


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
    except Exception as exc:
        logger.warning("Failed to update YAML description (%s): %s", name, exc)


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
    except Exception as exc:
        logger.warning("Failed to remove repo from YAML (%s): %s", name, exc)


@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"), headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.get("/app.js")
async def app_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="application/javascript", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.get("/ui.templates.js")
async def ui_templates_js():
    return FileResponse(str(FRONTEND_DIR / "ui.templates.js"), media_type="application/javascript", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.get("/app.css")
async def app_css():
    return FileResponse(str(FRONTEND_DIR / "app.css"), media_type="text/css", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.get("/app.template.html")
async def app_template():
    return FileResponse(str(FRONTEND_DIR / "app.template.html"), media_type="text/html", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
    })


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(str(FRONTEND_DIR / "favicon.svg"), media_type="image/svg+xml")


@app.get("/.well-known/appspecific/com.chrome.devtools.json", include_in_schema=False)
async def chrome_devtools_probe():
    # Chrome DevTools probes this path; return no content to avoid noisy 404 logs.
    return Response(status_code=204)


@app.get("/api/config")
async def config():
    installed_urls = list(get_installed_urls())
    return {"username": GITHUB_USERNAME, "avatar_url": get_avatar(),
            "installed_count": len(installed_urls),
            "installed_urls": installed_urls,
            "default_push_message": DEFAULT_PUSH_MESSAGE}


@app.get("/api/repos")
async def repos():
    yaml_repos = load_yaml_repos()
    sorted_repos = sorted(yaml_repos, key=lambda r: (r.get("name") != GITHUB_USERNAME,
                                                      str(r.get("name", "")).lower()))
    states_by_path, states_by_remote = get_local_git_states()

    enriched_github = []
    for repo in sorted_repos:
        enriched = dict(repo)
        can_push = False
        name = str(enriched.get("name", "")).strip()
        if name:
            local_path = MY_REPOS_DIR / name
            local_state = states_by_path.get(str(local_path.resolve()))
            if local_state:
                can_push = bool(local_state.get("can_push"))
        if not can_push:
            remote_state = states_by_remote.get(normalize_repo_url(enriched.get("url", "")))
            if remote_state:
                can_push = bool(remote_state.get("can_push"))
        enriched["can_push"] = can_push
        enriched_github.append(enriched)

    enriched_new = []
    for repo in get_new_projects(states_by_path):
        enriched = dict(repo)
        can_push = False
        raw_path = str(enriched.get("url", "")).strip()
        if raw_path:
            try:
                local_state = states_by_path.get(str(Path(raw_path).resolve()))
                if local_state:
                    can_push = bool(local_state.get("can_push"))
            except Exception as exc:
                logger.debug("Cannot resolve local path for can_push: %s", exc)
        enriched["can_push"] = can_push
        enriched_new.append(enriched)

    return {"repos": enriched_github + enriched_new, "count": len(sorted_repos)}


@app.get("/api/push-states")
async def push_states():
    yaml_repos = load_yaml_repos()
    sorted_repos = sorted(yaml_repos, key=lambda r: (r.get("name") != GITHUB_USERNAME,
                                                      str(r.get("name", "")).lower()))
    states_by_path, states_by_remote = get_local_git_states(force_refresh=True)

    items = []

    for repo in sorted_repos:
        name = str(repo.get("name", "")).strip()
        url = str(repo.get("url", "")).strip()
        can_push = False
        if name:
            preferred_local = BASE_DIR if BASE_DIR.name == name else (MY_REPOS_DIR / name)
            local_state = states_by_path.get(str(preferred_local.resolve()))
            if local_state:
                can_push = bool(local_state.get("can_push"))
        if not can_push:
            remote_state = states_by_remote.get(normalize_repo_url(url))
            if remote_state:
                can_push = bool(remote_state.get("can_push"))
        items.append({"name": name, "url": url, "can_push": can_push})

    for repo in get_new_projects(states_by_path):
        url = str(repo.get("url", "")).strip()
        can_push = False
        if url:
            try:
                local_state = states_by_path.get(str(Path(url).resolve()))
                if local_state:
                    can_push = bool(local_state.get("can_push"))
            except Exception as exc:
                logger.debug("Cannot resolve local path for push state: %s", exc)
        items.append({"name": str(repo.get("name", "")).strip(), "url": url, "can_push": can_push})

    return {"items": items}


@app.get("/api/project-screenshots")
async def project_screenshots(path: str = ""):
    resolved = resolve_project_path(path)
    if not resolved:
        raise HTTPException(404, "Folder not found")

    screenshots_dir = get_project_screenshots_dir(resolved)
    if not screenshots_dir.exists() or not screenshots_dir.is_dir():
        return {"items": []}

    items = []
    for file_path in sorted(screenshots_dir.iterdir(), key=lambda p: p.name.lower()):
        if not is_image_file(file_path):
            continue
        src = f"/api/project-screenshot-file?path={quote(str(resolved))}&name={quote(file_path.name)}"
        items.append({"name": file_path.name, "src": src})
    return {"items": items}


@app.get("/api/project-screenshot-file")
async def project_screenshot_file(path: str = "", name: str = ""):
    resolved = resolve_project_path(path)
    file_name = str(name or "").strip()
    if not resolved:
        raise HTTPException(404, "Folder not found")
    if not file_name:
        raise HTTPException(400, "Missing image name")

    screenshots_dir = get_project_screenshots_dir(resolved)
    candidate = (screenshots_dir / file_name).resolve()
    if screenshots_dir.resolve() not in candidate.parents:
        raise HTTPException(400, "Invalid image path")
    if not candidate.exists() or not is_image_file(candidate):
        raise HTTPException(404, "Image not found")

    media_type, _ = mimetypes.guess_type(str(candidate))
    return FileResponse(str(candidate), media_type=media_type or "application/octet-stream")


@app.post("/api/refresh")
async def refresh(request: Request):
    require_write_access(request)
    try:
        run_script(BACKEND_DIR / "get_all_github_projects.py", timeout=TIMEOUTS["refresh"])
        invalidate_runtime_caches()
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
        except Exception as exc:
            logger.debug("create-project script output is not JSON: %s", exc)
            if 'Project "' in output and '" created' in output:
                folder = output.split('Project "')[1].split('" created')[0]
        invalidate_runtime_caches()
        return {"success": True, "message": f'Project "{folder}" created' if folder else "Project created",
                "folder_name": folder}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/add-to-github")
async def add_to_github(payload: AddToGithubPayload, request: Request):
    require_write_access(request)
    name = payload.name.strip()
    description = payload.description.strip()
    visibility = payload.visibility.strip().lower() or "public"
    if not name or not safe_name(name):
        raise HTTPException(400, "Invalid project name")
    if visibility not in ("public", "private"):
        raise HTTPException(400, "Invalid visibility")

    source_path = NEW_PROJECTS_DIR / name
    if not source_path.exists() or not source_path.is_dir():
        raise HTTPException(404, f"Folder '{name}' not found")
    target_path = MY_REPOS_DIR / name
    if target_path.exists():
        raise HTTPException(400, f"Folder '{name}' already exists in MY_REPOS")

    commit_date = datetime.now().strftime("%d.%m.%Y")
    commit_message = f"v0.0.1 - {name} started {commit_date}"
    repo_slug = f"{GITHUB_USERNAME}/{name}" if GITHUB_USERNAME and GITHUB_USERNAME != "Unknown" else name

    try:
        # Move project into MY_REPOS first, then create/push GitHub repository from there.
        moved = False
        try:
            source_path.rename(target_path)
        except OSError:
            shutil.move(str(source_path), str(target_path))
        moved = True

        project_path = target_path
        if not (project_path / ".git").exists():
            run_command(["git", "init"], cwd=project_path, timeout=20)
        run_command(["git", "add", "."], cwd=project_path, timeout=60)
        run_command(["git", "commit", "--allow-empty", "-m", commit_message], cwd=project_path, timeout=60)

        visibility_flag = "--private" if visibility == "private" else "--public"
        gh_cmd = [
            "gh", "repo", "create", repo_slug, visibility_flag,
            "--description", description or "Local project folder",
            "--source", ".", "--remote", "origin", "--push",
        ]
        run_command(gh_cmd, cwd=project_path, timeout=120)

        run_script(BACKEND_DIR / "get_all_github_projects.py", timeout=TIMEOUTS["refresh"])
        invalidate_runtime_caches()
        return {
            "success": True,
            "name": name,
            "repo": repo_slug,
            "visibility": visibility,
            "commit_message": commit_message,
        }
    except Exception as e:
        try:
            if 'moved' in locals() and moved and target_path.exists() and not source_path.exists():
                target_path.rename(source_path)
        except Exception as rollback_exc:
            logger.error("Rollback failed for add-to-github %s: %s", name, rollback_exc)
        raise HTTPException(500, str(e))


@app.post("/api/install")
async def install(payload: InstallPayload, request: Request):
    require_write_access(request)
    urls = payload.repos
    if not urls:
        raise HTTPException(400, "No repositories selected")
    try:
        run_script(BACKEND_DIR / "install_existing_repo.py", [str(u) for u in urls],
                   timeout=TIMEOUTS["install_per_repo"] * len(urls))
        invalidate_runtime_caches()
        return {"success": True, "installed_count": count_folders(MY_REPOS_DIR)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/delete")
async def delete(payload: DeletePayload, request: Request):
    require_write_access(request)
    names = payload.repos
    if not names:
        raise HTTPException(400, "No repositories selected")
    try:
        run_script(BACKEND_DIR / "delete_local_folder.py", [str(n) for n in names],
                   timeout=TIMEOUTS["delete_per_repo"] * len(names))
        invalidate_runtime_caches()
        return {"success": True, "installed_count": count_folders(MY_REPOS_DIR),
                "new_projects_count": count_folders(NEW_PROJECTS_DIR)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/rename")
async def rename_local(payload: RenamePayload, request: Request):
    require_write_access(request)
    old, new = payload.old_name.strip(), payload.new_name.strip()
    if not old or not new or not safe_name(old) or not safe_name(new):
        raise HTTPException(400, "Invalid names")
    old_path, new_path = NEW_PROJECTS_DIR / old, NEW_PROJECTS_DIR / new
    if not old_path.exists():
        raise HTTPException(404, f"Folder '{old}' not found")
    if new_path.exists():
        raise HTTPException(400, f"Folder '{new}' already exists")
    old_path.rename(new_path)
    update_yaml_rename(old, new)
    invalidate_runtime_caches()
    return {"success": True, "old_name": old, "new_name": new}


@app.post("/api/rename-github")
async def rename_github(payload: RenamePayload, request: Request):
    require_write_access(request)
    old, new = payload.old_name.strip(), payload.new_name.strip()
    if not old or not new:
        raise HTTPException(400, "Invalid names")
    try:
        result = run_script(BACKEND_DIR / "rename_github_repo.py", [old, new],
                           timeout=TIMEOUTS["rename"])
        invalidate_runtime_caches()
        return {"success": True, "old_name": old, "new_name": new, "output": result.stdout}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/delete-github")
async def delete_github(payload: DeleteGithubPayload, request: Request):
    require_write_access(request)
    name = payload.name.strip()
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
            except Exception:
                detail = r.text
            raise HTTPException(500, f"GitHub API error {r.status_code}: {detail[:200]}")

        remove_repo_from_yaml(name)
        invalidate_runtime_caches()
        return {"success": True, "name": name}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/update-description")
async def update_description(payload: UpdateDescriptionPayload, request: Request):
    require_write_access(request)
    name = payload.name.strip()
    description = payload.description
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
            except Exception:
                detail = r.text
            raise HTTPException(500, f"GitHub API error {r.status_code}: {detail[:200]}")

        update_yaml_description(name, description)
        invalidate_runtime_caches()
        return {"success": True, "name": name, "description": description}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/open-folder")
async def open_folder(payload: OpenFolderPayload, request: Request):
    require_write_access(request)
    raw_path = payload.path.strip()
    resolved = resolve_project_path(raw_path)
    if not resolved:
        raise HTTPException(404, "Folder not found")

    try:
        run_script(BACKEND_DIR / "open_in_vscode.py", [str(resolved)], timeout=30)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"success": True, "path": str(resolved)}


@app.post("/api/open-folder-explorer")
async def open_folder_explorer(payload: OpenFolderPayload, request: Request):
    require_write_access(request)
    raw_path = payload.path.strip()
    resolved = resolve_project_path(raw_path)
    if not resolved:
        raise HTTPException(404, "Folder not found")

    try:
        open_folder_in_explorer(resolved)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"success": True, "path": str(resolved)}


@app.post("/api/push")
async def push_repo(payload: PushPayload, request: Request):
    require_write_access(request)
    raw_path = payload.path.strip()

    resolved = resolve_project_path(raw_path)
    if not resolved:
        raise HTTPException(404, "Folder not found")
    if not (resolved / ".git").exists():
        raise HTTPException(400, "Target folder is not a git repository")

    try:
        version_mode = str(getattr(payload, "version_mode", "use_existing") or "use_existing").strip().lower()
        if version_mode not in ("use_existing", "generate_version"):
            raise HTTPException(400, "Invalid version_mode")

        if version_mode == "generate_version":
            version_result = run_script(
                BACKEND_DIR / "create_new_version.py",
                [str(resolved)],
                timeout=30,
            )
            output_lines = [line.strip() for line in (version_result.stdout or "").splitlines() if line.strip()]
            commit_message = output_lines[-1] if output_lines else (payload.message.strip() or DEFAULT_PUSH_MESSAGE)
        else:
            commit_message = get_last_version_line(resolved)
            if not commit_message:
                raise HTTPException(400, "VERSION.md has no version lines. Select 'Generate Version' and try again.")

        run_command(["git", "add", "."], cwd=resolved, timeout=TIMEOUTS["git_push"])
        try:
            run_command(["git", "commit", "-m", commit_message], cwd=resolved, timeout=TIMEOUTS["git_push"])
        except Exception as e:
            msg = str(e).lower()
            if "nothing to commit" not in msg and "no changes added to commit" not in msg:
                raise
        branch_result = run_command(["git", "branch", "--show-current"], cwd=resolved, timeout=10)
        branch = (branch_result.stdout or "").strip() or "master"
        try:
            run_command(["git", "push", "origin", branch], cwd=resolved, timeout=TIMEOUTS["git_push"])
        except Exception as push_error:
            if not is_non_fast_forward_error(str(push_error)):
                raise
            run_command(["git", "pull", "--rebase", "origin", branch], cwd=resolved, timeout=TIMEOUTS["git_push"])
            run_command(["git", "push", "origin", branch], cwd=resolved, timeout=TIMEOUTS["git_push"])
        invalidate_runtime_caches()
        return {"success": True, "path": str(resolved), "message": commit_message}
    except Exception as e:
        raise HTTPException(500, str(e))
