/**
 * API Client Module
 * Handles all HTTP requests to the backend API
 */

const API = {
    baseURL: '',

    /**
     * Make an HTTP request to the API
     * @param {string} endpoint - API endpoint
     * @param {object} options - Fetch options
     * @returns {Promise<any>} - Response data
     */
    async request(endpoint, options = {}) {
        const url = this.baseURL + endpoint;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || data.error || `HTTP ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API request failed: ${endpoint}`, error);
            throw error;
        }
    },

    /**
     * GET request helper
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },

    /**
     * POST request helper
     */
    async post(endpoint, body = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(body),
        });
    },

    // ---- API Methods ----

    /**
     * Get application configuration
     */
    async getConfig() {
        return this.get('/api/config');
    },

    /**
     * Get all repositories
     */
    async getRepos() {
        return this.get('/api/repos');
    },

    /**
     * Refresh repositories list
     */
    async refreshRepos() {
        return this.post('/api/refresh');
    },

    /**
     * Create new project
     */
    async createProject() {
        return this.post('/api/create-project');
    },

    /**
     * Install repositories
     * @param {string[]} repoUrls - List of repository URLs to install
     */
    async installRepos(repoUrls) {
        return this.post('/api/install', { repos: repoUrls });
    },

    /**
     * Delete repositories
     * @param {string[]} repoNames - List of repository names to delete
     */
    async deleteRepos(repoNames) {
        return this.post('/api/delete', { repos: repoNames });
    },

    /**
     * Rename local project
     * @param {string} oldName - Current name
     * @param {string} newName - New name
     */
    async renameLocal(oldName, newName) {
        return this.post('/api/rename', { old_name: oldName, new_name: newName });
    },

    /**
     * Rename GitHub repository
     * @param {string} oldName - Current name
     * @param {string} newName - New name
     */
    async renameGithub(oldName, newName) {
        return this.post('/api/rename-github', { old_name: oldName, new_name: newName });
    },

    /**
     * Open folder in file explorer
     * @param {string} path - Folder path
     */
    async openFolder(path) {
        return this.post('/api/open-folder', { path });
    },
};
