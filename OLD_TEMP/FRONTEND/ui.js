/**
 * UI Rendering Module
 * Handles all DOM manipulation and rendering
 */

const UI = {
    // DOM element references
    elements: {},

    /**
     * Cache DOM element references
     */
    initElements() {
        this.elements = {
            navUsername: document.getElementById('nav-username'),
            navRepos: document.getElementById('nav-repos'),
            navInstalled: document.getElementById('nav-installed'),
            welcomeText: document.getElementById('welcome-text'),
            avatarContainer: document.getElementById('avatar-container'),
            avatarPlaceholder: document.getElementById('avatar-placeholder'),
            avatarImg: document.getElementById('avatar-img'),
            avatarMenu: document.getElementById('avatar-menu'),
            btnCreateNew: document.getElementById('btn-create-new'),
            btnRefresh: document.getElementById('btn-refresh'),
            confirmModal: document.getElementById('confirm-modal'),
            deleteModal: document.getElementById('delete-modal'),
            modalRepoList: document.getElementById('modal-repo-list'),
            modalDeleteRepoList: document.getElementById('modal-delete-repo-list'),
            modalCancel: document.getElementById('modal-cancel'),
            modalConfirm: document.getElementById('modal-confirm'),
            modalDeleteCancel: document.getElementById('modal-delete-cancel'),
            modalDeleteConfirm: document.getElementById('modal-delete-confirm'),
            reposTbody: document.getElementById('repos-tbody'),
            reposTable: document.getElementById('repos-table'),
        };
    },

    /**
     * Update header with current state
     */
    updateHeader() {
        const { navUsername, navRepos, navInstalled, avatarImg, avatarPlaceholder } = this.elements;

        navUsername.textContent = `👨 User: ${State.username}`;
        navRepos.textContent = `📦 Repos: ${State.count || 0}`;
        navInstalled.textContent = `📁 Installed: ${State.installedCount}`;

        if (State.avatarUrl) {
            avatarImg.src = State.avatarUrl;
            avatarImg.style.display = 'block';
            avatarPlaceholder.style.display = 'none';
        } else {
            avatarImg.style.display = 'none';
            avatarPlaceholder.style.display = 'flex';
        }
    },

    /**
     * Show welcome message
     * @param {string} message - Message to display
     */
    showWelcome(message) {
        this.elements.welcomeText.textContent = message;
        this.elements.welcomeText.className = 'welcome-text';
    },

    /**
     * Render the repositories table
     */
    renderTable() {
        const { reposTbody } = this.elements;
        reposTbody.innerHTML = '';

        State.repos.forEach(repo => {
            const isInstalled = State.isInstalled(repo);
            const isNewProject = repo.is_new_project || false;
            const rowClass = isNewProject ? 'new-project-row' : isInstalled ? 'installed-row' : '';

            const tr = document.createElement('tr');
            if (rowClass) tr.className = rowClass;
            tr.dataset.name = repo.name;
            tr.dataset.url = repo.url;
            tr.dataset.isNew = isNewProject;
            tr.dataset.isInstalled = isInstalled;

            const normalizedUrl = repo.url.endsWith('.git') ? repo.url.slice(0, -4) : repo.url;
            const logo = isNewProject ? '📁' : (repo.private ? '🔒' : '🌍');

            const createdDate = repo.created_at ? repo.created_at.slice(0, 10) : '';
            const createdTime = repo.created_at && repo.created_at.length > 11 ? repo.created_at.slice(11, 19) : '';

            tr.innerHTML = `
                <td class="logo-cell">
                    <span class="logo-icon" style="font-size:32px">📦</span>
                </td>
                <td class="name-cell" data-repo="${this.escapeHtml(repo.name)}" data-url="${this.escapeHtml(repo.url)}" title="Click to install/delete">
                    ${this.escapeHtml(repo.name)}
                </td>
                <td>${this.escapeHtml(repo.description || '')}</td>
                <td class="url-cell">
                    <a href="${this.escapeHtml(repo.url)}" class="url-link" data-url="${this.escapeHtml(repo.url)}" data-is-local="${isNewProject}">
                        ${logo}
                    </a>
                </td>
                <td>
                    <span class="date-badge">
                        ${createdDate}<br>${createdTime}
                    </span>
                </td>
            `;

            reposTbody.appendChild(tr);
        });
    },

    /**
     * Open action row for a repo
     * @param {HTMLElement} cell - Name cell element
     */
    openActionRow(cell) {
        const row = cell.closest('tr');
        const repoName = cell.dataset.repo;
        const repoUrl = cell.dataset.url;
        const isNewProject = row.dataset.isNew === 'true';
        const isInstalled = row.dataset.isInstalled === 'true';
        const isActive = cell.classList.contains('active');

        // Close all other action rows
        document.querySelectorAll('.name-cell.active').forEach(otherCell => {
            if (otherCell !== cell) {
                otherCell.classList.remove('active');
                const otherActionRow = otherCell.closest('tr').nextElementSibling;
                if (otherActionRow && otherActionRow.classList.contains('action-row')) {
                    otherActionRow.remove();
                }
            }
        });

        // Toggle current
        if (!isActive) {
            const actionRow = document.createElement('tr');
            actionRow.className = 'action-row';

            let buttons = '';
            if (isNewProject) {
                buttons = `
                    <button class="action-btn" data-action="delete" data-name="${this.escapeHtml(repoName)}" data-url="${this.escapeHtml(repoUrl)}">
                        <span class="action-btn-icon">🗑️</span>
                        <span class="action-btn-label">Delete</span>
                    </button>
                    <button class="action-btn" data-action="rename-local" data-name="${this.escapeHtml(repoName)}" data-url="${this.escapeHtml(repoUrl)}">
                        <span class="action-btn-icon">✏️</span>
                        <span class="action-btn-label">Rename</span>
                    </button>
                `;
            } else if (isInstalled) {
                buttons = `
                    <button class="action-btn" data-action="delete" data-name="${this.escapeHtml(repoName)}" data-url="${this.escapeHtml(repoUrl)}">
                        <span class="action-btn-icon">🗑️</span>
                        <span class="action-btn-label">Delete</span>
                    </button>
                    <button class="action-btn" data-action="rename-github" data-name="${this.escapeHtml(repoName)}" data-url="${this.escapeHtml(repoUrl)}">
                        <span class="action-btn-icon">✏️</span>
                        <span class="action-btn-label">Rename</span>
                    </button>
                `;
            } else {
                buttons = `
                    <button class="action-btn" data-action="install" data-name="${this.escapeHtml(repoName)}" data-url="${this.escapeHtml(repoUrl)}">
                        <span class="action-btn-icon">📥</span>
                        <span class="action-btn-label">Install</span>
                    </button>
                    <button class="action-btn" data-action="rename-github" data-name="${this.escapeHtml(repoName)}" data-url="${this.escapeHtml(repoUrl)}">
                        <span class="action-btn-icon">✏️</span>
                        <span class="action-btn-label">Rename</span>
                    </button>
                `;
            }

            const totalColumns = document.querySelector('thead tr').children.length;
            actionRow.innerHTML = `
                <td colspan="${totalColumns}" class="action-cell">${buttons}</td>
            `;

            row.parentNode.insertBefore(actionRow, row.nextSibling);
            actionRow.classList.add('show');
            cell.classList.add('active');
        } else {
            cell.classList.remove('active');
            const existingActionRow = row.nextElementSibling;
            if (existingActionRow && existingActionRow.classList.contains('action-row')) {
                existingActionRow.remove();
            }
        }
    },

    /**
     * Show install confirmation modal
     * @param {string} repoName - Repository name
     */
    showInstallModal(repoName) {
        this.elements.modalRepoList.textContent = repoName;
        this.elements.confirmModal.style.display = 'flex';
    },

    /**
     * Show delete confirmation modal
     * @param {string} repoName - Repository name
     */
    showDeleteModal(repoName) {
        this.elements.modalDeleteRepoList.textContent = repoName;
        this.elements.deleteModal.style.display = 'flex';
    },

    /**
     * Hide install modal
     */
    hideInstallModal() {
        this.elements.confirmModal.style.display = 'none';
    },

    /**
     * Hide delete modal
     */
    hideDeleteModal() {
        this.elements.deleteModal.style.display = 'none';
    },

    /**
     * Show avatar menu
     */
    showAvatarMenu() {
        this.elements.avatarMenu.style.display = 'flex';
    },

    /**
     * Hide avatar menu
     */
    hideAvatarMenu() {
        this.elements.avatarMenu.style.display = 'none';
    },

    /**
     * Update installed count display
     */
    updateInstalledCount() {
        this.elements.navInstalled.textContent = `📁 Installed: ${State.installedCount}`;
    },

    /**
     * Update repos count display
     */
    updateReposCount() {
        this.elements.navRepos.textContent = `📦 Repos: ${State.count || 0}`;
    },

    /**
     * Mark row as installed (visual only)
     * @param {string} repoUrl - Repository URL
     */
    markRowAsInstalled(repoUrl) {
        const row = document.querySelector(`tr[data-url="${CSS.escape(repoUrl)}"]`);
        if (row) {
            row.classList.add('installed-row');
            row.dataset.isInstalled = 'true';
        }
    },

    /**
     * Hide or remove a row
     * @param {string} repoName - Repository name
     * @param {string} repoUrl - Repository URL
     * @param {boolean} isNewProject - Is this a new project
     */
    removeRow(repoName, repoUrl, isNewProject) {
        const row = document.querySelector(`tr[data-name="${CSS.escape(repoName)}"]`);
        if (row) {
            if (isNewProject) {
                row.style.display = 'none';
            } else {
                row.classList.remove('installed-row');
                row.dataset.isInstalled = 'false';
            }
        }
    },

    /**
     * Escape HTML special characters
     * @param {string} str - Input string
     * @returns {string} - Escaped string
     */
    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    /**
     * Update sort indicators
     * @param {string} sortColumn - Current sort column
     * @param {number} sortDirection - Sort direction
     */
    updateSortIndicators(sortColumn, sortDirection) {
        document.querySelectorAll('th.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
            if (th.dataset.sort === sortColumn) {
                th.classList.add(sortDirection === 1 ? 'sort-asc' : 'sort-desc');
            }
        });
    },
};
