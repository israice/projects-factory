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

### 2.1 Configure functional settings

All function-level runtime settings are defined in `settings.yaml` (single source of truth):

```yaml
timeouts:
  refresh: 120
  create_project: 120
  install_per_repo: 300
  delete_per_repo: 60
  rename: 60
  git_remote: 5
  git_push: 120

create_project_repo_url: "https://github.com/israice/Create-Project-Folder.git"
cache:
  git_state_ttl_sec: 10
python:
  disable_bytecode: true
ui:
  default_push_message: "v0.0.2 - new table based dashboard"
```

`settings.yaml` is required at startup. Missing keys will stop the app with a clear error.

### 3. Get GitHub Token

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select scope **`repo`** (for private repos access)
4. Copy the token to `.env`

## Usage

### Start the server

```bash
python run.py
```

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

This creates/updates `BACKEND/get_all_github_projects.yaml` with your repos.

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
│   ├── get_all_github_projects.yaml
│   ├── install_existing_repo.py
│   ├── delete_local_folder.py
│   └── rename_github_repo.py
├── MY_REPOS/                 # Installed repositories
├── NEW_PROJECTS/             # Local project folders
├── OLD_TEMP/                 # Backup of old architecture (can delete)
├── requirements.txt          # Python dependencies
├── settings.yaml             # Configuration
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

### Frontend HMR (Vite)

For live frontend updates without full page reload, `python run.py` now starts both processes:

```bash
python run.py
```

Open:
- Frontend (Vite): http://127.0.0.1:5173
- Backend API: http://127.0.0.1:5999

One-time setup:

```bash
cd FRONTEND
npm install
```

If dependencies are missing, `python run.py` will auto-run `npm install` in `FRONTEND/`.

`vite.config.mjs` proxies `/api` and `/static` to FastAPI, so existing frontend API calls keep working.
When launched via `python run.py`, proxy target is passed automatically via env (`PF_BACKEND_HOST`, `PF_BACKEND_PORT`).
UI markup for hot updates is in `FRONTEND/app.template.html` (not in `index.html`).
Table/action-row markup templates are in `FRONTEND/ui.templates.js` and hot-reload without full page refresh.

Disable frontend dev server if needed:

```env
FRONTEND_HMR=0
```

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
