/**
 * State Management Module
 * Handles application state and data
 */

const State = {
    // Application state
    username: '',
    avatarUrl: '',
    installedCount: 0,
    repos: [],
    installedUrls: new Set(),
    count: 0,

    // UI state
    sortColumn: 'created_at',
    sortDirection: -1, // -1 = desc, 1 = asc
    pendingInstall: null,
    pendingDelete: null,
    activeRow: null,

    /**
     * Initialize state from server or API
     */
    async init() {
        // Check if server provided initial state (SSR mode)
        if (window.__INITIAL_STATE__) {
            console.log('Using server-provided initial state (SSR)');
            this.username = window.__INITIAL_STATE__.username;
            this.avatarUrl = window.__INITIAL_STATE__.avatarUrl;
            this.installedCount = window.__INITIAL_STATE__.installedCount;
            this.reposCount = window.__INITIAL_STATE__.reposCount;
            this.repos = window.__INITIAL_STATE__.repos || [];
            this.count = window.__INITIAL_STATE__.reposCount || 0;

            // Build set of installed URLs
            this.installedUrls = new Set(
                (window.__INITIAL_STATE__.installedUrls || []).map(url => {
                    let u = url;
                    if (u.endsWith('.git')) u = u.slice(0, -4);
                    return u.rstrip('/');
                })
            );

            // Clean up - remove global reference
            delete window.__INITIAL_STATE__;
            return; // No need to fetch from API
        }

        // Fallback: fetch from API (SPA mode)
        console.log('Fetching state from API (SPA mode)');
        try {
            const [config, reposData] = await Promise.all([
                API.getConfig(),
                API.getRepos(),
            ]);

            this.username = config.username;
            this.avatarUrl = config.avatar_url;
            this.installedCount = config.installed_count;

            this.repos = reposData.repos || [];
            this.count = reposData.count || 0;

            // Build set of installed URLs
            this.installedUrls = new Set(
                this.repos
                    .filter(r => !r.is_new_project)
                    .map(r => {
                        let url = r.url;
                        if (url.endsWith('.git')) url = url.slice(0, -4);
                        return url.rstrip('/');
                    })
            );

            console.log(`State initialized: ${this.repos.length} repos, ${this.installedCount} installed`);
        } catch (error) {
            console.error('Failed to initialize state:', error);
            throw error;
        }
    },

    /**
     * Check if a repo is installed
     * @param {object} repo - Repository object
     * @returns {boolean}
     */
    isInstalled(repo) {
        if (repo.is_new_project) return false;
        let url = repo.url;
        if (url.endsWith('.git')) url = url.slice(0, -4);
        url = url.rstrip('/');
        return this.installedUrls.has(url);
    },

    /**
     * Mark a repo as installed
     * @param {string} repoUrl - Repository URL
     */
    markAsInstalled(repoUrl) {
        let url = repoUrl;
        if (url.endsWith('.git')) url = url.slice(0, -4);
        url = url.rstrip('/');
        this.installedUrls.add(url);
        this.installedCount = this.installedUrls.size;
    },

    /**
     * Remove a repo from installed
     * @param {string} repoName - Repository name
     * @param {string} repoUrl - Repository URL
     */
    removeInstalled(repoName, repoUrl) {
        let url = repoUrl;
        if (url.endsWith('.git')) url = url.slice(0, -4);
        url = url.rstrip('/');
        this.installedUrls.delete(url);
        this.installedCount = this.installedUrls.size;

        // Remove from repos list if it's a new project
        if (repoUrl.includes('NEW_PROJECTS')) {
            this.repos = this.repos.filter(r => r.name !== repoName);
        }
    },

    /**
     * Rename a repo in state
     * @param {string} oldName - Old name
     * @param {string} newName - New name
     * @param {string} newUrl - New URL
     */
    renameRepo(oldName, newName, newUrl) {
        const repo = this.repos.find(r => r.name === oldName);
        if (repo) {
            repo.name = newName;
            repo.url = newUrl;
        }
    },

    /**
     * Sort repos by column
     * @param {string} column - Column to sort by
     */
    sortBy(column) {
        if (this.sortColumn === column) {
            this.sortDirection = -this.sortDirection;
        } else {
            this.sortColumn = column;
            this.sortDirection = 1;
        }

        const sorted = [...this.repos].sort((a, b) => {
            const aVal = String(a[column] || '').trim();
            const bVal = String(b[column] || '').trim();
            if (aVal < bVal) return -1 * this.sortDirection;
            if (aVal > bVal) return 1 * this.sortDirection;
            return 0;
        });

        this.repos = sorted;
    },

    /**
     * Get sort class for column header
     * @param {string} column - Column name
     * @returns {string}
     */
    getSortClass(column) {
        if (this.sortColumn !== column) return '';
        return this.sortDirection === 1 ? 'sort-asc' : 'sort-desc';
    },
};

// Helper for string prototype
if (!String.prototype.rstrip) {
    String.prototype.rstrip = function(chars) {
        let str = this;
        while (str.endsWith(chars || ' ')) {
            str = str.slice(0, -1);
        }
        return str;
    };
}
