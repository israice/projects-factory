# GitHub Projects Manager - Simplified Version

## What Changed

### Before (Old Architecture)
- **Backend**: `BACKEND/api/main.py` (600+ lines) - complex FastAPI with SSR templating
- **Frontend**: 4 separate JS files + CSS + HTML template
  - `FRONTEND/api.js` - API client
  - `FRONTEND/state.js` - State management  
  - `FRONTEND/ui.js` - UI rendering
  - `FRONTEND/app.js` - Main logic
  - `FRONTEND/styles.css` - Styles
  - `TEMPLATES/index.html` - Jinja2 SSR template

### After (Simplified)
- **Backend**: `main.py` (286 lines) - Clean FastAPI, no SSR
- **Frontend**: `FRONTEND/index.html` - Single file with inline JS + CSS

## Code Reduction

| Component | Before | After | Reduction |
|-----------|--------|-------|-----------|
| Backend | ~600 lines | 286 lines | ~52% |
| Frontend | ~800 lines (4 files) | ~450 lines (1 file) | ~44% |
| Files | 8 files | 2 files | 75% |

## Button Functionality (Unchanged)

All original button actions work exactly the same:

| Button | Action | API Endpoint | Backend Script Called |
|--------|--------|--------------|----------------------|
| **Create New** (avatar menu) | Create project folder | `/api/create-project` | `MY_REPOS/Create-Project-Folder/create_new_project.py` |
| **Refresh** (avatar menu) | Refresh GitHub repos list | `/api/refresh` | `BACKEND/get_all_github_projects.py` |
| **Install** (action row) | Git clone to MY_REPOS | `/api/install` | `BACKEND/install_existing_repo.py` |
| **Delete** (action row) | Delete local folder | `/api/delete` | `BACKEND/delete_local_folder.py` |
| **Rename** (action row, local) | Rename NEW_PROJECTS folder | `/api/rename` | Built-in Python `os.rename()` |
| **Rename** (action row, GitHub) | Rename GitHub repo | `/api/rename-github` | `BACKEND/rename_github_repo.py` |
| **Open Folder** (URL icon) | Open in file explorer | `/api/open-folder` | Built-in `subprocess.Popen(explorer)` |

## How to Run

```bash
# Option 1: Using run.py (updated)
python run.py

# Option 2: Direct main.py
python main.py

# Option 3: Using uvicorn
uvicorn main:app --reload --port 5999
```

Then open: **http://127.0.0.1:5999**

## Architecture

```
┌─────────────────────────────────────┐
│  FRONTEND/index.html                │
│  ├── HTML (structure)               │
│  ├── CSS (styles, inline)           │
│  └── JavaScript (all logic, inline) │
│      ├── State management           │
│      ├── API client                 │
│      ├── UI rendering               │
│      └── Event handlers             │
└─────────────────────────────────────┘
                ↕ REST API (JSON)
┌─────────────────────────────────────┐
│  main.py (FastAPI)                  │
│  ├── /api/config                    │
│  ├── /api/repos                     │
│  ├── /api/refresh                   │
│  ├── /api/create-project            │
│  ├── /api/install                   │
│  ├── /api/delete                    │
│  ├── /api/rename                    │
│  ├── /api/rename-github             │
│  └── /api/open-folder               │
└─────────────────────────────────────┘
```

## Key Simplifications

1. **No SSR (Server-Side Rendering)**: Pure SPA - simpler, faster client-side rendering
2. **No Jinja2 Templates**: HTML is static, data loaded via API
3. **No Module System**: All JS in one file - no import/export overhead
4. **No Separate CSS File**: Styles inline in `<style>` tag
5. **Simplified Backend**: Removed templating, complex state passing, SSR logic
6. **Direct File Serving**: FastAPI serves static `index.html` directly

## Files to Keep

Essential backend scripts (called by API):
- `BACKEND/get_all_github_projects.py`
- `BACKEND/get_all_github_projects.yaml`
- `BACKEND/install_existing_repo.py`
- `BACKEND/delete_local_folder.py`
- `BACKEND/rename_github_repo.py`
- `MY_REPOS/Create-Project-Folder/create_new_project.py`

Configuration:
- `.env` - GitHub credentials
- `settings.yaml` - Timeouts
- `requirements.txt` - Python dependencies

## Files That Can Be Removed (Old Architecture)

These are no longer used by the simplified version:
- `BACKEND/api/main.py` - Old complex backend
- `FRONTEND/api.js` - Now inline
- `FRONTEND/state.js` - Now inline
- `FRONTEND/ui.js` - Now inline
- `FRONTEND/app.js` - Now inline
- `FRONTEND/styles.css` - Now inline
- `TEMPLATES/index.html` - Old SSR template

## Testing

All functionality tested:
- ✅ API endpoints respond correctly
- ✅ Frontend loads and renders data
- ✅ Avatar displays user info
- ✅ Repository table shows GitHub + local projects
- ✅ Sorting works (name, description, URL, date)
- ✅ Action rows open/close on name click
- ✅ Install/Delete modals work
- ✅ Inline rename editing works
- ✅ URL links open folders/GitHub pages

## Next Steps

1. **Optional**: Delete old architecture files (backup first)
2. **Optional**: Further reduce by removing unused CSS classes
3. **Optional**: Add TypeScript for type safety
4. **Optional**: Add search/filter functionality
