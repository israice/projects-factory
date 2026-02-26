/**
 * Main application JavaScript for GitHub Repositories Manager
 */

document.addEventListener("DOMContentLoaded", function() {
    const nameCells = document.querySelectorAll(".name-cell");
    const installedCountEl = document.getElementById("installed-count");
    const modal = document.getElementById("confirm-modal");
    const modalRepoList = document.getElementById("modal-repo-list");
    const modalCancel = document.getElementById("modal-cancel");
    const modalConfirm = document.getElementById("modal-confirm");
    const welcomeText = document.getElementById("welcome-text");
    const deleteModal = document.getElementById("delete-modal");
    const modalDeleteRepoList = document.getElementById("modal-delete-repo-list");
    const modalDeleteCancel = document.getElementById("modal-delete-cancel");
    const modalDeleteConfirm = document.getElementById("modal-delete-confirm");
    const avatarContainer = document.getElementById("avatar-container");
    const avatarMenu = document.getElementById("avatar-menu");

    // Toggle avatar menu on avatar click
    if (avatarContainer && avatarMenu) {
        avatarContainer.addEventListener("click", function(e) {
            e.stopPropagation();
            const isHidden = avatarMenu.style.display === "none" || avatarMenu.style.display === "";
            // Close all other menus first
            if (avatarMenu) avatarMenu.style.display = "none";
            // Toggle this menu
            if (isHidden) {
                avatarMenu.style.display = "flex";
            }
        });
    }

    // Close avatar menu when clicking outside
    document.addEventListener("click", function(e) {
        if (avatarMenu && !avatarContainer.contains(e.target)) {
            avatarMenu.style.display = "none";
        }
    });

    // Check for message in URL and store in sessionStorage, then clean URL
    const urlParams = new URLSearchParams(window.location.search);
    const message = urlParams.get("message");
    if (message) {
        sessionStorage.setItem("welcomeMessage", message);
        window.history.replaceState({}, "", window.location.pathname);
    }

    // Display stored message if available
    const storedMessage = sessionStorage.getItem("welcomeMessage");
    if (storedMessage) {
        welcomeText.textContent = storedMessage;
        sessionStorage.removeItem("welcomeMessage");
    }

    let sortColumn = "created_at";
    let sortDirection = -1;
    let pendingInstall = null;
    let pendingDelete = null;

    // Get table structure dynamically
    const table = document.querySelector("table");
    const headerRow = table.querySelector("tr:first-child");
    const totalColumns = headerRow.children.length;

    // Find created_at column index dynamically
    const createdAtTh = headerRow.querySelector('[data-sort="created_at"]');
    const createdAtIndex = createdAtTh ? Array.from(headerRow.children).indexOf(createdAtTh) : totalColumns - 1;

    // Sort by created_at column by default (descending - newest first)
    const rows = Array.from(table.querySelectorAll("tr:not(:first-child)"));
    document.querySelectorAll("th.sortable").forEach(h => h.classList.remove("sort-asc", "sort-desc"));
    if (createdAtTh) {
        createdAtTh.classList.add("sort-desc");
        rows.sort((a, b) => {
            const aVal = a.cells[createdAtIndex].textContent.trim();
            const bVal = b.cells[createdAtIndex].textContent.trim();
            if (aVal < bVal) return 1;
            if (aVal > bVal) return -1;
            return 0;
        });
        rows.forEach(row => table.appendChild(row));
    }
    table.insertBefore(headerRow, table.firstChild);

    // Toggle action row on name cell click
    nameCells.forEach(cell => {
        cell.addEventListener("click", function(e) {
            e.stopPropagation();
            openActionRow(this);
        });
    });

    // Handle URL link clicks
    const urlLinks = document.querySelectorAll(".url-link");
    urlLinks.forEach(link => {
        link.addEventListener("click", function(e) {
            const isLocal = this.dataset.isLocal === "true";
            
            // Only handle left-click (button 0)
            // Middle-click (button 1) and right-click should use default browser behavior
            if (e.button !== 0) return;
            
            e.preventDefault();
            e.stopPropagation();
            const url = this.dataset.url;

            if (isLocal) {
                // Open local folder via backend
                fetch("/open-folder", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path: url })
                }).catch(err => console.error("Failed to open folder:", err));
            } else {
                // Open GitHub URL in same tab
                window.location.href = url;
            }
        });
    });

    function openActionRow(cell) {
        const row = cell.closest("tr");
        const repoName = cell.dataset.repo;
        const repoUrl = cell.dataset.url;
        const isActive = cell.classList.contains("active");

        // Reset all cells
        nameCells.forEach(otherCell => {
            otherCell.classList.remove("active");
            const otherActionRow = otherCell.closest("tr").nextElementSibling;
            if (otherActionRow && otherActionRow.classList.contains("action-row")) {
                otherActionRow.classList.remove("show");
            }
        });

        // Toggle current
        if (!isActive) {
            let actionRow = row.nextElementSibling;
            const isInstalled = row.classList.contains("installed-row");
            const isNewProject = row.classList.contains("new-project-row");
            if (!actionRow || !actionRow.classList.contains("action-row")) {
                actionRow = document.createElement("tr");
                actionRow.className = "action-row";
                actionRow.id = "bottom-panel-" + repoName;
                // Show Delete+Rename for new projects, Delete for installed, Install for non-installed
                if (isInstalled || isNewProject) {
                    if (isNewProject) {
                        actionRow.innerHTML = '<td colspan="' + totalColumns + '" class="action-cell"><button class="action-btn" data-action="delete" data-name="' + repoName + '" data-url="' + repoUrl + '"><span class="action-btn-icon">🗑️</span><span class="action-btn-label">Delete</span></button><button class="action-btn" data-action="rename-local" data-name="' + repoName + '" data-url="' + repoUrl + '"><span class="action-btn-icon">✏️</span><span class="action-btn-label">Rename</span></button></td>';
                    } else {
                        actionRow.innerHTML = '<td colspan="' + totalColumns + '" class="action-cell"><button class="action-btn" data-action="delete" data-name="' + repoName + '" data-url="' + repoUrl + '"><span class="action-btn-icon">🗑️</span><span class="action-btn-label">Delete</span></button><button class="action-btn" data-action="rename-github" data-name="' + repoName + '" data-url="' + repoUrl + '"><span class="action-btn-icon">✏️</span><span class="action-btn-label">Rename</span></button></td>';
                    }
                } else {
                    actionRow.innerHTML = '<td colspan="' + totalColumns + '" class="action-cell"><button class="action-btn" data-action="install" data-name="' + repoName + '" data-url="' + repoUrl + '"><span class="action-btn-icon">📥</span><span class="action-btn-label">Install</span></button><button class="action-btn" data-action="rename-github" data-name="' + repoName + '" data-url="' + repoUrl + '"><span class="action-btn-icon">✏️</span><span class="action-btn-label">Rename</span></button></td>';
                }
                row.parentNode.insertBefore(actionRow, row.nextSibling);
            }
            actionRow.classList.add("show");
            cell.classList.add("active");
        }
    }

    // Handle action button clicks and outside clicks
    document.addEventListener("click", function(e) {
        // Ignore clicks on URL links - they have their own handler
        const urlLink = e.target.closest(".url-link");
        if (urlLink) return;
        
        const actionBtn = e.target.closest(".action-btn");
        const nameCell = e.target.closest(".name-cell");
        const actionRow = e.target.closest(".action-row");

        // If clicking outside of action rows and name cells, close all action rows
        if (!nameCell && !actionRow) {
            nameCells.forEach(cell => {
                cell.classList.remove("active");
                const row = cell.closest("tr").nextElementSibling;
                if (row && row.classList.contains("action-row")) {
                    row.classList.remove("show");
                }
            });
        }

        if (!actionBtn) return;
        e.stopPropagation();
        e.preventDefault();
        const action = actionBtn.dataset.action;
        const repoName = actionBtn.dataset.name;
        const repoUrl = actionBtn.dataset.url;
        if (action === "install") {
            pendingInstall = { name: repoName, url: repoUrl };
            modalRepoList.textContent = repoName;
            modal.style.display = "flex";
        } else if (action === "delete") {
            pendingDelete = { name: repoName, url: repoUrl };
            modalDeleteRepoList.textContent = repoName;
            deleteModal.style.display = "flex";
        } else if (action === "rename-local") {
            const nameCell = document.querySelector(`.name-cell[data-repo="${repoName}"]`);
            if (nameCell) {
                makeCellEditable(nameCell, "/rename");
            }
        } else if (action === "rename-github") {
            const nameCell = document.querySelector(`.name-cell[data-repo="${repoName}"]`);
            if (nameCell) {
                makeCellEditable(nameCell, "/rename-github");
            }
        } else if (action === "open") {
            window.open(repoUrl, "_blank");
        } else if (action === "settings") {
            window.open(repoUrl, "_blank");
        }
    });

    // Make cell editable and save on blur
    function makeCellEditable(cell, endpoint = "/rename") {
        const originalName = cell.dataset.repo;
        const input = document.createElement("input");
        input.type = "text";
        input.value = originalName;
        input.style.width = "90%";
        input.style.padding = "4px";
        input.style.background = "#404040";
        input.style.color = "#e0e0e0";
        input.style.border = "1px solid #4CAF50";
        input.style.borderRadius = "4px";
        input.style.fontSize = "inherit";
        input.style.fontFamily = "inherit";

        cell.textContent = "";
        cell.appendChild(input);
        input.focus();
        input.select();

        async function saveValue() {
            const newName = input.value.trim();
            if (newName && newName !== originalName) {
                try {
                    const response = await fetch(endpoint, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ old_name: originalName, new_name: newName })
                    });
                    const data = await response.json();
                    if (data.success) {
                        cell.textContent = newName;
                        cell.dataset.repo = newName;
                        // Update URL if it contains the old name
                        const oldUrl = cell.dataset.url;
                        if (oldUrl && oldUrl.includes(originalName)) {
                            cell.dataset.url = oldUrl.replace(originalName, newName);
                        }
                        // Update action row buttons with new name
                        const actionRow = cell.closest("tr").nextElementSibling;
                        if (actionRow && actionRow.classList.contains("action-row")) {
                            const actionBtns = actionRow.querySelectorAll(".action-btn");
                            actionBtns.forEach(btn => {
                                if (btn.dataset.name === originalName) {
                                    btn.dataset.name = newName;
                                }
                            });
                        }
                        // Close action row
                        const actionRow2 = cell.closest("tr").nextElementSibling;
                        if (actionRow2 && actionRow2.classList.contains("action-row")) {
                            actionRow2.classList.remove("show");
                        }
                        welcomeText.textContent = "✅ Renamed to " + newName;
                    } else {
                        welcomeText.textContent = "❌ Rename failed: " + data.error;
                        cell.textContent = originalName;
                    }
                } catch (err) {
                    welcomeText.textContent = "❌ Request failed: " + err.message;
                    cell.textContent = originalName;
                }
            } else {
                cell.textContent = originalName;
            }
        }

        input.addEventListener("blur", saveValue);
        input.addEventListener("keydown", function(e) {
            if (e.key === "Enter") {
                input.blur();
            } else if (e.key === "Escape") {
                cell.textContent = originalName;
            }
        });
    }

    modalCancel.addEventListener("click", function() {
        modal.style.display = "none";
        pendingInstall = null;
    });
    modalConfirm.addEventListener("click", async function() {
        if (!pendingInstall) return;
        modal.style.display = "none";
        welcomeText.textContent = "⏳ Installing " + pendingInstall.name + "...";
        try {
            const response = await fetch("/install", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repos: [pendingInstall.url] })
            });
            const data = await response.json();
            if (data.success) {
                if (data.installed_count !== undefined && installedCountEl) {
                    installedCountEl.textContent = "📁 Installed: " + data.installed_count;
                }
                welcomeText.textContent = "✅ Installed " + pendingInstall.name;
                const nameCell = document.querySelector(`.name-cell[data-url="${pendingInstall.url}"]`);
                if (nameCell) {
                    nameCell.classList.remove("active");
                    nameCell.closest("tr").classList.add("installed-row");
                    const actionRow = nameCell.closest("tr").nextElementSibling;
                    if (actionRow && actionRow.classList.contains("action-row")) {
                        actionRow.classList.remove("show");
                    }
                }
            } else {
                welcomeText.textContent = "❌ Installation failed";
            }
        } catch (err) {
            welcomeText.textContent = "❌ Request failed: " + err.message;
        }
        pendingInstall = null;
    });
    modal.addEventListener("click", function(e) {
        if (e.target === modal) {
            modal.style.display = "none";
            pendingInstall = null;
        }
    });

    modalDeleteCancel.addEventListener("click", function() {
        deleteModal.style.display = "none";
        pendingDelete = null;
    });
    modalDeleteConfirm.addEventListener("click", async function() {
        if (!pendingDelete) return;
        deleteModal.style.display = "none";
        welcomeText.textContent = "⏳ Deleting " + pendingDelete.name + "...";
        try {
            const response = await fetch("/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ repos: [pendingDelete.name] })
            });
            const data = await response.json();
            if (data.success) {
                if (data.installed_count !== undefined && installedCountEl) {
                    installedCountEl.textContent = "📁 Installed: " + data.installed_count;
                }
                welcomeText.textContent = "✅ Deleted " + pendingDelete.name;
                const nameCell = document.querySelector(`.name-cell[data-url="${pendingDelete.url}"]`);
                if (nameCell) {
                    nameCell.classList.remove("active");
                    const row = nameCell.closest("tr");
                    row.classList.remove("installed-row", "new-project-row");
                    // Remove the row for new projects, or just remove installed class for MY_REPOS
                    if (pendingDelete.url.includes("NEW_PROJECTS")) {
                        row.style.display = "none";
                    }
                    const actionRow = row.nextElementSibling;
                    if (actionRow && actionRow.classList.contains("action-row")) {
                        actionRow.classList.remove("show");
                    }
                }
            } else {
                welcomeText.textContent = "❌ Deletion failed";
            }
        } catch (err) {
            welcomeText.textContent = "❌ Request failed: " + err.message;
        }
        pendingDelete = null;
    });
    deleteModal.addEventListener("click", function(e) {
        if (e.target === deleteModal) {
            deleteModal.style.display = "none";
            pendingDelete = null;
        }
    });

    welcomeText.addEventListener("click", function() {
        welcomeText.textContent = "Добро пожаловать, Мастер";
        welcomeText.className = "welcome-text";
    });

    // Sorting functionality
    document.querySelectorAll("th.sortable").forEach(th => {
        th.addEventListener("click", function() {
            const column = this.dataset.sort;
            const table = this.closest("table");
            const headerRow = table.querySelector("tr:first-child");
            // Exclude action rows from sorting
            const rows = Array.from(table.querySelectorAll("tr:not(:first-child):not(.action-row)"));
            if (sortColumn === column) {
                sortDirection = -sortDirection;
            } else {
                sortColumn = column;
                sortDirection = 1;
            }
            document.querySelectorAll("th.sortable").forEach(h => h.classList.remove("sort-asc", "sort-desc"));
            this.classList.add(sortDirection === 1 ? "sort-asc" : "sort-desc");

            // Get column index dynamically
            const columnIndex = Array.from(headerRow.children).indexOf(this);

            rows.sort((a, b) => {
                const aVal = a.cells[columnIndex].textContent.trim();
                const bVal = b.cells[columnIndex].textContent.trim();
                if (aVal < bVal) return -1 * sortDirection;
                if (aVal > bVal) return 1 * sortDirection;
                return 0;
            });
            rows.forEach(row => table.appendChild(row));
            table.insertBefore(headerRow, table.firstChild);
        });
    });
});
