# GitHub Projects Manager v3.0 - Simplified

Modern web application for managing GitHub repositories and local project folders.

## Architecture

**Ultra-simplified Single Page Application (SPA):**

```
┌─────────────────────────────────────┐
│  FRONTEND/index.html                │
│  ├── HTML (structure)               │
│  ├── CSS (inline styles)            │
│  └── JavaScript (inline, all logic) │
└─────────────────────────────────────┘
                ↕ REST API (JSON)
┌─────────────────────────────────────┐
│  BACKEND/main.py (FastAPI)          │
└─────────────────────────────────────┘
```

## Features

- **View all repositories** - GitHub repos + local project folders in one table
- **Install repositories** - Clone GitHub repos to `MY_REPOS/`
- **Delete projects** - Remove local folders from `MY_REPOS/` or `NEW_PROJECTS/`
- **Rename projects** - Rename local folders or GitHub repositories
- **Open folders** - Open project folders in system file explorer
- **Live avatar** - Display GitHub user avatar
- **Sorting** - Sort by name, description, URL, or creation date
- **Dark theme** - Easy on the eyes for late-night coding sessions

## Installation

### 1. Clone and setup

```bash
cd C:\0_PROJECTS\projects-factory
pip install -r requirements.txt
```

### 2. Configure environment

Create `.env` file in the project root:

```env
GITHUB_USERNAME=your-github-username
GITHUB_TOKEN=your-personal-access-token
PORT=5999
LOG_LEVEL=INFO
```

Bitwarden option (recommended for secrets):
- Keep only non-secret values in `.env`.
- Use Bitwarden Secrets Manager CLI (`bws`) with:
  - `BITWARDEN_ENABLED=1`
  - `BITWARDEN_PROVIDER=auto` (or `bws`)
  - `BWS_ACCESS_TOKEN=...`
  - `BWS_PROJECT_ID=...`
  - `BWS_GITHUB_TOKEN_SECRET=GITHUB_TOKEN`
  - `BWS_GITHUB_USERNAME_SECRET=GITHUB_USERNAME`
  - `BWS_REQUIRE_WRITE=1` (startup probe for `create/update/delete`)

### 2.1 Configure functional settings

All function-level runtime settings are defined in `SETTINGS.py` (single source of truth):

```python
TIMEOUT_REFRESH = 120
TIMEOUT_CREATE_PROJECT = 120
TIMEOUT_INSTALL_PER_REPO = 300
TIMEOUT_DELETE_PER_REPO = 60
TIMEOUT_RENAME = 60
TIMEOUT_GIT_REMOTE = 5
TIMEOUT_GIT_PUSH = 120
CREATE_PROJECT_REPO_URL = "https://github.com/israice/Create-Project-Folder.git"
GIT_STATE_TTL_SEC = 10
PYTHONDONTWRITEBYTECODE = "1"
SERVER_PORT = 5001
SERVER_HOST = "127.0.0.1"
```

`SETTINGS.py` is required at startup.

### 3. Get GitHub Token

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select scope **`repo`** (for private repos access)
4. Store the token in Bitwarden (recommended) or in `.env`

## Usage

### Start the server

```bash
python run.py
```

Start with Bitwarden (`bws`) and still use `python run.py`:

```powershell
$env:BITWARDEN_ENABLED="1"
$env:BITWARDEN_PROVIDER="bws"  # or "auto"
$env:BWS_ACCESS_TOKEN="your-access-token"
$env:BWS_PROJECT_ID="your-project-id"
$env:BWS_REQUIRE_WRITE="1"
python run.py
```

Bitwarden (`bws`) mapping:
- secret key `GITHUB_TOKEN` -> env `GITHUB_TOKEN`
- secret key `GITHUB_USERNAME` -> env `GITHUB_USERNAME`

Or directly with uvicorn:

```bash
uvicorn BACKEND.main:app --port 5999
```

Open in browser: **http://127.0.0.1:5999**

### Fetch repositories list

Before using the web interface, fetch your GitHub repositories:

```bash
python BACKEND/get_all_github_projects.py
```

This validates access and prints how many repositories are available via GitHub API.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get user config (username, avatar, installed count) |
| GET | `/api/repos` | Get all repositories (GitHub + local) |
| POST | `/api/refresh` | Refresh GitHub repositories list |
| POST | `/api/create-project` | Create new project folder |
| POST | `/api/install` | Install repositories (git clone) |
| POST | `/api/delete` | Delete local folders |
| POST | `/api/rename` | Rename local project |
| POST | `/api/rename-github` | Rename GitHub repository |
| POST | `/api/push` | Run git add/commit/push for a local project |
| POST | `/api/open-folder` | Open folder in file explorer |
| GET | `/` | Serve frontend (index.html) |

## Project Structure

```
projects-factory/
├── run.py                    # Entry point
├── FRONTEND/
│   └── index.html            # All-in-one frontend (HTML+CSS+JS)
├── BACKEND/
│   ├── main.py               # FastAPI backend (single file)
│   ├── get_all_github_projects.py
│   ├── install_existing_repo.py
│   ├── delete_local_folder.py
│   └── rename_github_repo.py
├── MY_REPOS/                 # Installed repositories
├── NEW_PROJECTS/             # Local project folders
├── OLD_TEMP/                 # Backup of old architecture (can delete)
├── requirements.txt          # Python dependencies
├── SETTINGS.py               # Configuration
└── .env                      # Environment variables
```

## v3.0 Simplification

### What Changed from v2.0

1. **Backend**: `BACKEND/api/main.py` (600 lines) → `BACKEND/main.py` (single file)
2. **Frontend**: 4 JS files + CSS → Single `FRONTEND/index.html`
3. **No SSR**: Removed Jinja2 templating, pure SPA
4. **75% fewer files**: Old architecture backed up to `OLD_TEMP/`

### Migration from v2.0

The old architecture is backed up in `OLD_TEMP/`. You can safely delete it:

```bash
# After confirming v3.0 works:
rmdir /S OLD_TEMP
```

### Running v3.0

```bash
python run.py
# or
uvicorn BACKEND.main:app --port 5999
```

## Development

### Backend Reload

Backend auto-restart on Python file changes:

```bash
uvicorn BACKEND.main:app --reload --port 5999
```

When running `python run.py`, backend hot reload is enabled by default.
Disable it with:

```env
HOT_RELOAD=0
```

### Frontend Dev HMR

`python run.py` starts backend + Vite HMR automatically.

Open frontend at:
- `http://127.0.0.1:5173`

Notes:
- edit `FRONTEND/app.template.html`, `FRONTEND/ui.templates.js`, `FRONTEND/app.css`, `FRONTEND/app.js`
- avoid editing `FRONTEND/index.html` during dev (that one may still trigger full reload)

### API Documentation

Interactive API docs available at:
- Swagger UI: http://127.0.0.1:5999/docs
- ReDoc: http://127.0.0.1:5999/redoc

## Troubleshooting

### Port already in use

Change the port in `.env`:

```env
PORT=5000
```

### Git not found

Ensure Git is installed and in your PATH:

```bash
git --version
```

### GitHub API rate limit

If you hit rate limits, ensure your `GITHUB_TOKEN` is set correctly in `.env`.

## License

MIT License - see LICENSE file for details.
