# Timeouts
# Timeout for full GitHub repos refresh operation (seconds).
TIMEOUT_REFRESH = 120
# Timeout for creating a new local project (seconds).
TIMEOUT_CREATE_PROJECT = 120
# Per-repository timeout for install/clone operations (seconds).
TIMEOUT_INSTALL_PER_REPO = 300
# Per-repository timeout for local delete operations (seconds).
TIMEOUT_DELETE_PER_REPO = 60
# Timeout for repository rename operation (seconds).
TIMEOUT_RENAME = 60
# Timeout for short git remote/status checks (seconds).
TIMEOUT_GIT_REMOTE = 5
# Timeout for git add/commit/push/pull --rebase operations (seconds).
TIMEOUT_GIT_PUSH = 120

# Git / Project
# Git URL for auto-installing Create-Project-Folder helper repo.
CREATE_PROJECT_REPO_URL = "https://github.com/israice/Create-Project-Folder.git"
# Reserved base directory name for local-only projects (informational).
BASE_DIRECTORY = "NEW_PROJECTS"
# TTL for cached local git state in backend memory (seconds).
GIT_STATE_TTL_SEC = 10

# Runtime
# Disables .pyc/__pycache__ generation when set to "1"/"true"/"yes"/"on".
PYTHONDONTWRITEBYTECODE = "1"

# Server
# Backend API port to bind (must be integer >= 1).
SERVER_PORT = 5001
# Backend host/interface to bind (for local-only use keep 127.0.0.1).
SERVER_HOST = "127.0.0.1"
