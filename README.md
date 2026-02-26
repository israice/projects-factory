# GitHub Projects Manager v2.0

Modern web application for managing GitHub repositories and local project folders.

## Architecture

This is a **Single Page Application (SPA)** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (SPA - Vanilla JS)                            │
│  ├── index.html          # Main HTML template           │
│  ├── styles.css          # All styles                   │
│  ├── api.js              # API client module            │
│  ├── state.js            # State management             │
│  ├── ui.js               # UI rendering                 │
│  └── app.js              # Main application logic       │
└─────────────────────────────────────────────────────────┘
                          ↕ REST API (JSON)
┌─────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI)                                      │
│  └── api/main.py         # API endpoints + static serve │
└─────────────────────────────────────────────────────────┘
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
```

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
uvicorn BACKEND.api.main:app --reload --port 5999
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
| POST | `/api/open-folder` | Open folder in file explorer |

## Project Structure

```
projects-factory/
├── BACKEND/
│   ├── api/
│   │   └── main.py           # FastAPI application
│   ├── get_all_github_projects.py
│   ├── get_all_github_projects.yaml
│   ├── install_existing_repo.py
│   ├── delete_local_folder.py
│   └── rename_github_repo.py
├── FRONTEND/
│   ├── index.html            # SPA entry point
│   ├── styles.css            # Application styles
│   ├── api.js                # API client
│   ├── state.js              # State management
│   ├── ui.js                 # UI rendering
│   └── app.js                # Main logic
├── MY_REPOS/                 # Installed repositories
├── NEW_PROJECTS/             # Local project folders
├── run.py                    # Server entry point
├── requirements.txt          # Python dependencies
├── settings.yaml             # Configuration
└── .env                      # Environment variables
```

## Migration from v1.x

### Key Changes

1. **Backend**: Flask → FastAPI
2. **Frontend**: Server-rendered templates → Client-side SPA
3. **API**: Mixed redirects/AJAX → Consistent REST API
4. **Structure**: Monolithic `run.py` → Modular architecture

### Breaking Changes

- None for end users - UI looks and behaves the same
- API endpoints changed from `/install` to `/api/install`, etc.
- No more server-side template rendering

### Upgrade Steps

1. Update dependencies: `pip install -r requirements.txt`
2. Replace `run.py` with new version
3. Replace `FRONTEND/` files with new SPA version
4. Add `BACKEND/api/main.py`
5. Start server: `python run.py`

## Development

### Hot Reload

For development with auto-reload:

```bash
uvicorn BACKEND.api.main:app --reload --port 5999
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
