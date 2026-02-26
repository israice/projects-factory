# OLD_TEMP - Backup of Old Architecture (v2.0)

This folder contains the old project structure that was replaced in v3.0.

## Contents

- `BACKEND/api/` - Old complex FastAPI backend (~600 lines)
- `FRONTEND/*.js` - Old separate JavaScript modules (api.js, state.js, ui.js, app.js)
- `FRONTEND/styles.css` - Old separate CSS file
- `TEMPLATES/` - Old Jinja2 SSR templates

## Can I Delete This?

**Yes!** Once you've confirmed v3.0 works correctly, you can safely delete this entire folder.

## How to Delete

```bash
# Windows
rmdir /S OLD_TEMP

# Linux/Mac
rm -rf OLD_TEMP
```

## What Replaced These Files?

| Old Files | New File |
|-----------|----------|
| `BACKEND/api/main.py` | `main.py` (simplified) |
| `FRONTEND/api.js` | `FRONTEND/index.html` (inline) |
| `FRONTEND/state.js` | `FRONTEND/index.html` (inline) |
| `FRONTEND/ui.js` | `FRONTEND/index.html` (inline) |
| `FRONTEND/app.js` | `FRONTEND/index.html` (inline) |
| `FRONTEND/styles.css` | `FRONTEND/index.html` (inline) |
| `TEMPLATES/index.html` | `FRONTEND/index.html` |

## Version Info

- **Backed up from**: v2.0
- **Replaced by**: v3.0 Simplified
- **Date**: 2026-02-26
