/**
 * Main Application Entry Point
 * Initializes the app and handles user interactions
 */

// ---- Initialization ----

document.addEventListener('DOMContentLoaded', async function() {
    try {
        // Initialize modules
        UI.initElements();
        await State.init();
        
        // Check if table was server-rendered (SSR mode)
        const hasServerRows = document.querySelectorAll('#repos-tbody tr').length > 0;
        
        if (hasServerRows) {
            console.log('Using server-rendered table (SSR)');
            // Just update header, table is already rendered
            UI.updateHeader();
        } else {
            console.log('Rendering table client-side (SPA)');
            UI.updateHeader();
            UI.renderTable();
        }
        
        applyInitialSort();
        setupEventListeners();

        // Check for welcome message from previous action
        checkWelcomeMessage();

        console.log('Application initialized successfully');
    } catch (error) {
        console.error('Failed to initialize application:', error);
        UI.showWelcome('❌ Failed to load: ' + error.message);
    }
});

// ---- Event Listeners Setup ----

function setupEventListeners() {
    // Avatar menu toggle
    UI.elements.avatarContainer.addEventListener('click', function(e) {
        e.stopPropagation();
        if (UI.elements.avatarMenu.style.display === 'none' || !UI.elements.avatarMenu.style.display) {
            UI.showAvatarMenu();
        } else {
            UI.hideAvatarMenu();
        }
    });

    // Close avatar menu on outside click
    document.addEventListener('click', function(e) {
        if (!UI.elements.avatarContainer.contains(e.target)) {
            UI.hideAvatarMenu();
        }
    });

    // Avatar menu actions
    UI.elements.btnCreateNew.addEventListener('click', async function(e) {
        e.preventDefault();
        UI.hideAvatarMenu();
        await handleCreateProject();
    });

    UI.elements.btnRefresh.addEventListener('click', async function(e) {
        e.preventDefault();
        UI.hideAvatarMenu();
        await handleRefresh();
    });

    // Welcome text click to reset
    UI.elements.welcomeText.addEventListener('click', function() {
        UI.showWelcome('Добро пожаловать, Мастер');
    });

    // Table sorting
    document.querySelectorAll('th.sortable').forEach(th => {
        th.addEventListener('click', function() {
            const column = this.dataset.sort;
            State.sortBy(column);
            UI.renderTable();
            UI.updateSortIndicators(State.sortColumn, State.sortDirection);
        });
    });

    // Name cell clicks (open action row)
    document.addEventListener('click', function(e) {
        const nameCell = e.target.closest('.name-cell');
        if (nameCell) {
            e.stopPropagation();
            UI.openActionRow(nameCell);
        }
    });

    // URL link clicks
    document.addEventListener('click', function(e) {
        const urlLink = e.target.closest('.url-link');
        if (urlLink) {
            e.preventDefault();
            e.stopPropagation();
            handleUrlClick(urlLink);
        }
    });

    // Action button clicks
    document.addEventListener('click', function(e) {
        const actionBtn = e.target.closest('.action-btn');
        if (actionBtn) {
            e.preventDefault();
            e.stopPropagation();
            handleActionButton(actionBtn);
        }
    });

    // Modal: Cancel install
    UI.elements.modalCancel.addEventListener('click', function() {
        UI.hideInstallModal();
        State.pendingInstall = null;
    });

    // Modal: Confirm install
    UI.elements.modalConfirm.addEventListener('click', function() {
        UI.hideInstallModal();
        if (State.pendingInstall) {
            handleInstallConfirm(State.pendingInstall);
            State.pendingInstall = null;
        }
    });

    // Modal: Cancel delete
    UI.elements.modalDeleteCancel.addEventListener('click', function() {
        UI.hideDeleteModal();
        State.pendingDelete = null;
    });

    // Modal: Confirm delete
    UI.elements.modalDeleteConfirm.addEventListener('click', function() {
        UI.hideDeleteModal();
        if (State.pendingDelete) {
            handleDeleteConfirm(State.pendingDelete);
            State.pendingDelete = null;
        }
    });

    // Close modals on overlay click
    UI.elements.confirmModal.addEventListener('click', function(e) {
        if (e.target === UI.elements.confirmModal) {
            UI.hideInstallModal();
            State.pendingInstall = null;
        }
    });

    UI.elements.deleteModal.addEventListener('click', function(e) {
        if (e.target === UI.elements.deleteModal) {
            UI.hideDeleteModal();
            State.pendingDelete = null;
        }
    });
}

// ---- Action Handlers ----

async function handleCreateProject() {
    UI.showWelcome('⏳ Creating project...');
    try {
        const result = await API.createProject();
        UI.showWelcome(result.message || '✅ Project created');

        // Reload data
        await State.init();
        UI.updateHeader();
        UI.renderTable();
        applyInitialSort();
    } catch (error) {
        UI.showWelcome('❌ Create failed: ' + error.message);
    }
}

async function handleRefresh() {
    UI.showWelcome('⏳ Refreshing...');
    try {
        const result = await API.refreshRepos();
        UI.showWelcome(result.message || '✅ Refreshed');

        // Reload data
        await State.init();
        UI.updateHeader();
        UI.renderTable();
        applyInitialSort();
    } catch (error) {
        UI.showWelcome('❌ Refresh failed: ' + error.message);
    }
}

function handleUrlClick(link) {
    const isLocal = link.dataset.isLocal === 'true';
    const url = link.dataset.url;

    if (isLocal) {
        // Open local folder via API
        API.openFolder(url).catch(err => console.error('Failed to open folder:', err));
    } else {
        // Open GitHub URL in same tab
        window.location.href = url;
    }
}

function handleActionButton(btn) {
    const action = btn.dataset.action;
    const repoName = btn.dataset.name;
    const repoUrl = btn.dataset.url;

    switch (action) {
        case 'install':
            State.pendingInstall = { name: repoName, url: repoUrl };
            UI.showInstallModal(repoName);
            break;
        case 'delete':
            State.pendingDelete = { name: repoName, url: repoUrl };
            UI.showDeleteModal(repoName);
            break;
        case 'rename-local':
            makeCellEditable(repoName, repoUrl, '/api/rename');
            break;
        case 'rename-github':
            makeCellEditable(repoName, repoUrl, '/api/rename-github');
            break;
    }
}

async function handleInstallConfirm(repo) {
    UI.showWelcome('⏳ Installing ' + repo.name + '...');
    try {
        const result = await API.installRepos([repo.url]);

        State.markAsInstalled(repo.url);
        UI.updateInstalledCount();
        UI.markRowAsInstalled(repo.url);
        UI.showWelcome('✅ Installed ' + repo.name);

        // Close action row
        closeActionRow(repo.url);
    } catch (error) {
        UI.showWelcome('❌ Install failed: ' + error.message);
    }
}

async function handleDeleteConfirm(repo) {
    UI.showWelcome('⏳ Deleting ' + repo.name + '...');
    try {
        const result = await API.deleteRepos([repo.name]);

        const isNewProject = repo.url.includes('NEW_PROJECTS');
        State.removeInstalled(repo.name, repo.url);
        UI.updateInstalledCount();
        UI.removeRow(repo.name, repo.url, isNewProject);
        UI.showWelcome('✅ Deleted ' + repo.name);
    } catch (error) {
        UI.showWelcome('❌ Delete failed: ' + error.message);
    }
}

// ---- Rename Functionality ----

function makeCellEditable(repoName, repoUrl, endpoint) {
    const cell = document.querySelector(`.name-cell[data-repo="${CSS.escape(repoName)}"]`);
    if (!cell) return;

    const originalName = cell.dataset.repo;
    const input = document.createElement('input');
    input.type = 'text';
    input.value = originalName;
    input.className = 'rename-input';
    input.style.cssText = `
        width: 90%;
        padding: 4px;
        background: #404040;
        color: #e0e0e0;
        border: 1px solid #4CAF50;
        border-radius: 4px;
        font-size: inherit;
        font-family: inherit;
    `;

    cell.textContent = '';
    cell.appendChild(input);
    input.focus();
    input.select();

    async function saveValue() {
        const newName = input.value.trim();
        if (newName && newName !== originalName) {
            try {
                const apiMethod = endpoint.includes('rename-github') ? 'renameGithub' : 'renameLocal';
                const result = await API[apiMethod](originalName, newName);

                // Update state
                const newUrl = updateUrlWithName(repoUrl, originalName, newName);
                State.renameRepo(originalName, newName, newUrl);

                // Update UI
                cell.textContent = newName;
                cell.dataset.repo = newName;
                cell.dataset.url = newUrl;

                // Update action row buttons
                updateActionRowButtons(originalName, newName);

                // Update pending operations
                if (State.pendingDelete && State.pendingDelete.name === originalName) {
                    State.pendingDelete.name = newName;
                }
                if (State.pendingInstall && State.pendingInstall.name === originalName) {
                    State.pendingInstall.name = newName;
                }

                UI.showWelcome('✅ Renamed to ' + newName);
                closeActionRow(newUrl);
            } catch (error) {
                UI.showWelcome('❌ Rename failed: ' + error.message);
                cell.textContent = originalName;
            }
        } else {
            cell.textContent = originalName;
        }
    }

    input.addEventListener('blur', saveValue);
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            input.blur();
        } else if (e.key === 'Escape') {
            cell.textContent = originalName;
        }
    });
}

function updateUrlWithName(url, oldName, newName) {
    if (!url) return url;

    // Local path pattern
    if (url.includes('NEW_PROJECTS') || url.includes('MY_REPOS') || url.startsWith('file://')) {
        const pattern = new RegExp(`[/\\\\]${escapeRegExp(oldName)}$`);
        if (pattern.test(url)) {
            return url.replace(pattern, '/' + newName);
        }
        return url;
    }

    // GitHub URL pattern
    const githubPattern = new RegExp(`[/\\\\]${escapeRegExp(oldName)}[/\\\\]?$`);
    if (githubPattern.test(url)) {
        return url.replace(githubPattern, '/' + newName);
    }

    return url;
}

function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function updateActionRowButtons(oldName, newName) {
    const actionRow = document.querySelector(`tr[data-name="${CSS.escape(oldName)}"] + .action-row`);
    if (actionRow) {
        actionRow.querySelectorAll('.action-btn').forEach(btn => {
            if (btn.dataset.name === oldName) {
                btn.dataset.name = newName;
            }
        });
    }
}

function closeActionRow(repoUrl) {
    const row = document.querySelector(`tr[data-url="${CSS.escape(repoUrl)}"]`);
    if (row) {
        row.classList.remove('active');
        const actionRow = row.nextElementSibling;
        if (actionRow && actionRow.classList.contains('action-row')) {
            actionRow.remove();
        }
    }
}

// ---- Sorting ----

function applyInitialSort() {
    // Sort by created_at descending by default
    State.sortColumn = 'created_at';
    State.sortDirection = -1;
    State.sortBy('created_at');
    UI.renderTable();
    UI.updateSortIndicators(State.sortColumn, State.sortDirection);
}

// ---- Welcome Message from Session ----

function checkWelcomeMessage() {
    const message = sessionStorage.getItem('welcomeMessage');
    if (message) {
        UI.showWelcome(message);
        sessionStorage.removeItem('welcomeMessage');
    }
}
