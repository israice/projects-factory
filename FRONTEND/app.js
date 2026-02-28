import appTemplateRaw from "./app.template.html?raw";
import * as UiTemplates from "./ui.templates.js";

const normalizeRepoUrl = (url = '') => String(url).replace(/\.git$/, '').replace(/\/$/, '');
        let appEventController = null;
        let templateApi = UiTemplates;
        let appTemplate = appTemplateRaw;
        const hotData = import.meta.hot?.data || {};
        const isHotModuleReload = !!hotData.wasMounted;
        const hotSnapshot = hotData.snapshot || null;
        const hotState = hotData.state || null;
        function setTextIfChanged(el, value) {
            if (!el) return;
            const next = String(value ?? '');
            if (el.textContent !== next) el.textContent = next;
        }
        function recalcRowNumbers(repos) {
            const ordered = [...repos].sort((a, b) => {
                const dt = getCreatedAtMs(b.created_at) - getCreatedAtMs(a.created_at);
                if (dt !== 0) return dt;
                return String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' });
            });
            const map = new Map(ordered.map((repo, idx) => [`${repo.name}|${repo.url}`, ordered.length - idx]));
            repos.forEach(repo => { repo.__rowNo = map.get(`${repo.name}|${repo.url}`) || 0; });
        }
        function recalcStateCounters() {
            State.localOnlyCount = State.repos.filter(r => !!r.is_new_project).length;
            State.count = State.repos.filter(r => !r.is_new_project).length;
            State.installedCount = State.installedUrls.size;
            recalcRowNumbers(State.repos);
        }
        function captureStateSnapshot() {
            return {
                username: State.username,
                avatarUrl: State.avatarUrl,
                installedCount: State.installedCount,
                repos: Array.isArray(State.repos) ? [...State.repos] : [],
                count: State.count,
                installedUrls: Array.from(State.installedUrls || []),
                localOnlyCount: State.localOnlyCount,
                lastLaunchedRowNo: State.lastLaunchedRowNo,
                localDescriptions: State.localDescriptions || {},
                defaultPushMessage: State.defaultPushMessage || '',
            };
        }
        function restoreStateSnapshot(snapshot) {
            if (!snapshot || typeof snapshot !== 'object') return false;
            State.username = snapshot.username || '';
            State.avatarUrl = snapshot.avatarUrl || '';
            State.installedCount = Number(snapshot.installedCount || 0);
            State.repos = Array.isArray(snapshot.repos) ? [...snapshot.repos] : [];
            State.count = Number(snapshot.count || 0);
            State.installedUrls = new Set(Array.isArray(snapshot.installedUrls) ? snapshot.installedUrls : []);
            State.localOnlyCount = Number(snapshot.localOnlyCount || 0);
            State.lastLaunchedRowNo = snapshot.lastLaunchedRowNo ?? null;
            State.localDescriptions = snapshot.localDescriptions && typeof snapshot.localDescriptions === 'object'
                ? snapshot.localDescriptions
                : {};
            State.defaultPushMessage = String(snapshot.defaultPushMessage || '');
            recalcRowNumbers(State.repos);
            return true;
        }
        const LAST_URL_ROW_KEY = 'projectsFactory:lastUrlRowNo';
        const LOCAL_DESC_KEY = 'projectsFactory:localDescriptions';

        function readLocalDescriptions() {
            try {
                const raw = localStorage.getItem(LOCAL_DESC_KEY);
                const parsed = raw ? JSON.parse(raw) : {};
                return parsed && typeof parsed === 'object' ? parsed : {};
            } catch {
                return {};
            }
        }

        function writeLocalDescriptions(map) {
            try {
                localStorage.setItem(LOCAL_DESC_KEY, JSON.stringify(map || {}));
            } catch {}
        }

        function setLocalDescription(name, description) {
            const key = String(name || '').trim();
            if (!key) return;
            const map = readLocalDescriptions();
            if (description) map[key] = description;
            else delete map[key];
            writeLocalDescriptions(map);
        }

        function removeLocalDescription(name) {
            const key = String(name || '').trim();
            if (!key) return;
            const map = readLocalDescriptions();
            if (!(key in map)) return;
            delete map[key];
            writeLocalDescriptions(map);
        }

        function renameLocalDescription(oldName, newName) {
            const oldKey = String(oldName || '').trim();
            const newKey = String(newName || '').trim();
            if (!oldKey || !newKey || oldKey === newKey) return;
            const map = readLocalDescriptions();
            if (!(oldKey in map)) return;
            map[newKey] = map[oldKey];
            delete map[oldKey];
            writeLocalDescriptions(map);
        }

        const ConfirmDialog = {
            el: null,
            resolve: null,

            init(signal) {
                this.el = {
                    overlay: document.getElementById('confirm-overlay'),
                    message: document.getElementById('confirm-message'),
                    ok: document.getElementById('confirm-ok'),
                    cancel: document.getElementById('confirm-cancel')
                };
                this.el.ok.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.close(true);
                }, { signal });
                this.el.cancel.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.close(false);
                }, { signal });
                this.el.overlay.addEventListener('click', (e) => {
                    if (e.target === this.el.overlay) this.close(false);
                }, { signal });
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape' && this.resolve) this.close(false);
                }, { signal });
            },

            open(message, opts = {}) {
                const { confirmText = 'Confirm', danger = false } = opts;
                if (this.resolve) this.close(false);
                this.el.message.textContent = message || '';
                this.el.ok.textContent = confirmText;
                this.el.ok.classList.toggle('confirm-danger', !!danger);
                return new Promise((resolve) => {
                    this.resolve = resolve;
                    this.el.overlay.hidden = false;
                    this.el.ok.focus();
                });
            },

            close(result) {
                if (!this.resolve) return;
                const done = this.resolve;
                this.resolve = null;
                this.el.overlay.hidden = true;
                done(!!result);
            }
        };

        const ImagePreview = {
            el: null,
            openSrc: '',

            init(signal) {
                this.el = {
                    overlay: document.getElementById('image-preview-overlay'),
                    image: document.getElementById('image-preview-img')
                };
                this.close();
                this.el.overlay.addEventListener('click', () => this.close(), { signal });
                this.el.image.addEventListener('click', () => this.close(), { signal });
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') this.close();
                }, { signal });
                document.addEventListener('click', (e) => {
                    const trigger = e.target?.closest?.('.screenshot-item[data-preview-src]');
                    if (!trigger) return;
                    e.preventDefault();
                    e.stopPropagation();
                    const src = String(trigger.dataset.previewSrc || '').trim();
                    const alt = String(trigger.dataset.previewAlt || '').trim();
                    if (!src) return;
                    if (!this.el.overlay.hidden && this.openSrc === src) {
                        this.close();
                        return;
                    }
                    this.open(src, alt);
                }, { signal });
            },

            open(src, alt = 'preview') {
                if (!this.el?.overlay || !this.el?.image) return;
                this.openSrc = src;
                this.el.image.src = src;
                this.el.image.alt = alt || 'preview';
                this.el.overlay.hidden = false;
            },

            close() {
                if (!this.el?.overlay || !this.el?.image) return;
                this.openSrc = '';
                this.el.overlay.hidden = true;
                this.el.image.removeAttribute('src');
                this.el.image.alt = '';
            }
        };

        async function refreshDataAndView(withServerRefresh = false) {
            if (withServerRefresh) await API.post('/api/refresh', {});
            await State.init();
            UI.updateHeader();
            UI.renderTable();
        }

        function formatCreated(value = '') {
            if (!value) return '-';
            const [datePart, timePart = ''] = String(value).split('T');
            const cleanTime = timePart.replace('Z', '').slice(0, 5);
            if (!datePart) return '-';
            return { date: datePart, time: cleanTime || '--:--' };
        }

        function getCreatedAtMs(value = '') {
            const ts = Date.parse(String(value || ''));
            return Number.isFinite(ts) ? ts : -1;
        }

        // State
        const State = {
            username: '', avatarUrl: '', installedCount: 0, repos: [], count: 0,
            installedUrls: new Set(),
            localOnlyCount: 0,
            lastLaunchedRowNo: null,
            localDescriptions: {},
            defaultPushMessage: '',

            async init() {
                const [config, reposData] = await Promise.all([
                    fetch('/api/config').then(r => r.json()),
                    fetch('/api/repos').then(r => r.json())
                ]);
                this.username = config.username;
                this.avatarUrl = config.avatar_url;
                this.installedCount = config.installed_count;
                this.defaultPushMessage = String(config.default_push_message || '').trim();
                const repos = reposData.repos || [];
                const orderedForRowNo = [...repos].sort((a, b) => {
                    const dt = getCreatedAtMs(b.created_at) - getCreatedAtMs(a.created_at);
                    if (dt !== 0) return dt;
                    return String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' });
                });
                const rowNoMap = new Map(
                    orderedForRowNo.map((repo, idx) => [`${repo.name}|${repo.url}`, orderedForRowNo.length - idx])
                );
                this.repos = repos.map(repo => ({
                    ...repo,
                    __rowNo: rowNoMap.get(`${repo.name}|${repo.url}`) || 0
                }));
                this.localDescriptions = readLocalDescriptions();
                this.repos.forEach(repo => {
                    if (!repo.is_new_project) return;
                    const localDesc = this.localDescriptions[repo.name];
                    if (typeof localDesc === 'string') repo.description = localDesc;
                });
                this.localOnlyCount = this.repos.filter(r => r.is_new_project).length;
                this.count = reposData.count || 0;
                // installedUrls comes from config (actual installed repos from MY_REPOS)
                this.installedUrls = new Set(
                    (config.installed_urls || []).map(normalizeRepoUrl)
                );
                const savedRowNo = Number(localStorage.getItem(LAST_URL_ROW_KEY) || 0);
                this.lastLaunchedRowNo = savedRowNo > 0 ? savedRowNo : null;
            },
            isInstalled(repo) {
                if (repo.is_new_project) return false;
                const url = normalizeRepoUrl(repo.url);
                return this.installedUrls.has(url);
            },

            getLaunchableRepos() {
                return [...this.repos]
                    .filter(r => Number(r.__rowNo) > 0)
                    .sort((a, b) => Number(a.__rowNo) - Number(b.__rowNo));
            },

            getNextLaunchRepo() {
                const launchable = this.getLaunchableRepos();
                if (!launchable.length) return null;
                const last = Number(this.lastLaunchedRowNo || 0);
                return launchable.find(r => Number(r.__rowNo) > last) || launchable[0];
            }
        };

        // API
        const API = {
            async request(endpoint, options = {}) {
                const r = await fetch(endpoint, {
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    },
                    ...options
                });
                const text = await r.text();
                let data = {};
                try { data = text ? JSON.parse(text) : {}; } catch {}
                if (!r.ok) throw new Error(data.detail || data.error || text || `HTTP ${r.status}`);
                return data;
            },
            get: (endpoint) => API.request(endpoint, { method: 'GET' }),
            post: (endpoint, body) => API.request(endpoint, { method: 'POST', body: JSON.stringify(body) }),
            getProjectScreenshots: (path) => API.get(`/api/project-screenshots?path=${encodeURIComponent(path || '')}`),
            installRepos: (urls) => API.post('/api/install', { repos: urls }),
            pushRepo: (path, message, versionMode = 'use_existing') => API.post('/api/push', { path, message, version_mode: versionMode }),
            addToGithub: (name, description, visibility = 'public') => API.post('/api/add-to-github', { name, description, visibility }),
            deleteRepos: (names) => API.post('/api/delete', { repos: names }),
            deleteGithubRepo: (name) => API.post('/api/delete-github', { name }),
            renameLocal: (old, new_) => API.post('/api/rename', { old_name: old, new_name: new_ }),
            renameGithub: (old, new_) => API.post('/api/rename-github', { old_name: old, new_name: new_ }),
            updateDescription: (name, description) => API.post('/api/update-description', { name, description }),
            openFolder: (path) => API.post('/api/open-folder', { path }),
            openFolderExplorer: (path) => API.post('/api/open-folder-explorer', { path }),
            createProject: () => API.post('/api/create-project')
        };

        // UI
        const UI = {
            el: {},
            sortKey: 'created_at',
            sortDir: 'desc',
            welcomeTimer: null,
            clockTimer: null,
            init() {
                if (this.clockTimer) {
                    clearInterval(this.clockTimer);
                    this.clockTimer = null;
                }
                this.el = {
                    username: document.getElementById('nav-username'),
                    repos: document.getElementById('nav-repos'),
                    installed: document.getElementById('nav-installed'),
                    localOnly: document.getElementById('nav-local-only'),
                    lastUrl: document.getElementById('nav-last-url'),
                    clock: document.getElementById('nav-clock'),
                    welcome: document.getElementById('welcome-text'),
                    avatarContainer: document.getElementById('avatar-container'),
                    avatarImg: document.getElementById('avatar-img'),
                    avatarPlaceholder: document.getElementById('avatar-placeholder'),
                    search: document.getElementById('table-search'),
                    tbody: document.getElementById('repos-tbody'),
                    headers: Array.from(document.querySelectorAll('#repos-table thead th[data-sort]'))
                };
                this.updateSortHeader();
                this.startClock();
            },
            updateClock() {
                if (!this.el.clock) return;
                const now = new Date();
                const hh = String(now.getHours());
                const mm = String(now.getMinutes()).padStart(2, '0');
                const ss = String(now.getSeconds()).padStart(2, '0');
                setTextIfChanged(this.el.clock, `🕒 ${hh}:${mm}:${ss}`);
            },
            startClock() {
                this.updateClock();
                this.clockTimer = setInterval(() => this.updateClock(), 1000);
            },
            setSort(key) {
                if (this.sortKey === key) {
                    this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
                } else {
                    this.sortKey = key;
                    this.sortDir = key === 'created_at' ? 'desc' : 'asc';
                }
                this.updateSortHeader();
                this.renderTable();
            },
            updateSortHeader() {
                if (!this.el.headers) return;
                this.el.headers.forEach(h => {
                    h.classList.remove('sort-asc', 'sort-desc');
                    if (h.dataset.sort === this.sortKey) {
                        h.classList.add(this.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
                    }
                });
            },
            getSortedRepos() {
                const list = [...State.repos];
                const dir = this.sortDir === 'asc' ? 1 : -1;
                const cmpText = (a, b) => String(a || '').localeCompare(String(b || ''), undefined, { sensitivity: 'base' });
                list.sort((a, b) => {
                    let result = 0;
                    switch (this.sortKey) {
                        case 'name':
                            result = cmpText(a.name, b.name);
                            break;
                        case 'description':
                            result = cmpText(a.description, b.description);
                            break;
                        case 'url':
                            result = cmpText(a.url, b.url);
                            break;
                        case 'created_at': {
                            result = getCreatedAtMs(a.created_at) - getCreatedAtMs(b.created_at);
                            break;
                        }
                        case 'type': {
                            const weight = (repo) => repo.is_new_project ? 0 : (repo.private ? 1 : 2);
                            result = weight(a) - weight(b);
                            break;
                        }
                        default:
                            result = 0;
                    }
                    return result * dir;
                });
                return list;
            },
            getFilteredRepos() {
                const query = String(this.el.search?.value || '').trim().toLowerCase();
                if (!query) return this.getSortedRepos();
                const tokens = query.split(/\s+/).filter(Boolean);
                return this.getSortedRepos().filter(repo => {
                    const created = formatCreated(repo.created_at);
                    const haystack = [
                        repo.name,
                        repo.description,
                        repo.url,
                        created.date,
                        created.time,
                        repo.private ? 'private lock' : 'public globe',
                        repo.is_new_project ? 'local folder' : 'github'
                    ].join(' ').toLowerCase();
                    return tokens.every(token => haystack.includes(token));
                });
            },
            updateHeader() {
                setTextIfChanged(this.el.username, State.username || '-');
                setTextIfChanged(this.el.repos, `📦 Repos: ${State.count}`);
                setTextIfChanged(this.el.installed, `📁 Downloaded: ${State.installedCount}`);
                setTextIfChanged(this.el.localOnly, `🗂️ New Projects: ${State.localOnlyCount}`);
                const nextRepo = State.getNextLaunchRepo();
                setTextIfChanged(this.el.lastUrl, `🚀 Next: ${nextRepo ? Number(nextRepo.__rowNo) : '-'}`);
                if (State.avatarUrl) {
                    if (this.el.avatarImg.src !== State.avatarUrl) this.el.avatarImg.src = State.avatarUrl;
                    this.el.avatarImg.style.display = 'block';
                    this.el.avatarPlaceholder.style.display = 'none';
                } else {
                    this.el.avatarImg.style.display = 'none';
                    this.el.avatarPlaceholder.style.display = 'flex';
                }
            },
            showWelcome(msg) {
                this.el.welcome.textContent = msg || '';
                if (this.welcomeTimer) clearTimeout(this.welcomeTimer);
                if (msg) {
                    this.welcomeTimer = setTimeout(() => {
                        this.el.welcome.textContent = '';
                        this.welcomeTimer = null;
                    }, 5000);
                }
            },
            markLastUrlLaunch(rowNo) {
                State.lastLaunchedRowNo = rowNo || null;
                if (State.lastLaunchedRowNo) localStorage.setItem(LAST_URL_ROW_KEY, String(State.lastLaunchedRowNo));
                else localStorage.removeItem(LAST_URL_ROW_KEY);
                this.updateHeader();
            },
            buildRowKey(repo) {
                return `${repo.name}|${repo.url}`;
            },
            patchRepoRow(tr, repo, installed) {
                const isNew = repo.is_new_project;
                const rowClass = isNew ? 'new-project-row' : installed ? 'installed-row' : '';
                const logoClass = repo.can_push ? 'logo-cell has-unpushed' : 'logo-cell';
                const logo = isNew ? '📁' : (repo.private ? '🔒' : '🌍');
                const created = formatCreated(repo.created_at);
                const nextHtml = templateApi.renderRepoRow({
                    repo,
                    created,
                    isNew,
                    logoClass,
                    logo,
                    escape: this.escape
                });
                if (tr.innerHTML !== nextHtml) tr.innerHTML = nextHtml;
                tr.className = rowClass;
                tr.dataset.key = this.buildRowKey(repo);
                tr.dataset.name = repo.name;
                tr.dataset.url = repo.url;
                tr.dataset.isNew = isNew ? 'true' : 'false';
                tr.dataset.installed = installed ? 'true' : 'false';
                tr.dataset.canPush = repo.can_push ? 'true' : 'false';
            },
            patchActionRowForRepo(repoUrl) {
                const row = document.querySelector(`tr[data-url="${CSS.escape(repoUrl || '')}"]`);
                if (!row) return;
                const actionRow = row.nextElementSibling;
                if (!actionRow || !actionRow.classList.contains('action-row')) return;
                const name = row.dataset.name || '';
                const url = row.dataset.url || '';
                const isNew = row.dataset.isNew === 'true';
                const installed = row.dataset.installed === 'true';
                const canPush = row.dataset.canPush === 'true';
                const buttons = templateApi.renderActionButtons({
                    isNew,
                    installed,
                    canPush,
                    name,
                    url,
                    isHttpUrl,
                    escape: this.escape
                });
                const nextHtml = templateApi.renderActionRowCell(buttons);
                if (actionRow.innerHTML !== nextHtml) actionRow.innerHTML = nextHtml;
                loadProjectScreenshots(actionRow, { name, url });
            },
            renderTable() {
                const tbody = this.el.tbody;
                const activeUrl = document.querySelector('.logo-cell.active')?.dataset?.url || '';
                this.closeAllActionRows();
                tbody.querySelectorAll('tr.action-row').forEach(r => r.remove());

                const repos = this.getFilteredRepos();
                const desiredKeys = new Set(repos.map(repo => this.buildRowKey(repo)));
                const existingRows = new Map(
                    Array.from(tbody.querySelectorAll('tr[data-key]')).map(row => [row.dataset.key, row])
                );

                existingRows.forEach((row, key) => {
                    if (!desiredKeys.has(key)) row.remove();
                });

                repos.forEach((repo, index) => {
                    const key = this.buildRowKey(repo);
                    let tr = existingRows.get(key);
                    if (!tr) tr = document.createElement('tr');
                    this.patchRepoRow(tr, repo, State.isInstalled(repo));
                    const currentAtIndex = tbody.children[index];
                    if (currentAtIndex !== tr) tbody.insertBefore(tr, currentAtIndex || null);
                });
                if (activeUrl) {
                    const activeCell = document.querySelector(`.logo-cell[data-url="${CSS.escape(activeUrl)}"]`);
                    if (activeCell) this.openActionRow(activeCell);
                }
            },
            openActionRow(cell) {
                const row = cell.closest('tr');
                const name = cell.dataset.repo;
                const url = cell.dataset.url;
                const isNew = row.dataset.isNew === 'true';
                const installed = row.dataset.installed === 'true';
                const canPush = row.dataset.canPush === 'true';
                const active = cell.classList.contains('active');

                this.closeAllActionRows(cell);

                if (!active) {
                    const actionRow = document.createElement('tr');
                    actionRow.className = 'action-row show';
                    const buttons = templateApi.renderActionButtons({
                        isNew,
                        installed,
                        canPush,
                        name,
                        url,
                        isHttpUrl,
                        escape: this.escape
                    });
                    actionRow.innerHTML = templateApi.renderActionRowCell(buttons);
                    row.parentNode.insertBefore(actionRow, row.nextSibling);
                    cell.classList.add('active');
                    loadProjectScreenshots(actionRow, { name, url });
                } else {
                    cell.classList.remove('active');
                    const ar = row.nextElementSibling;
                    if (ar && ar.classList.contains('action-row')) ar.remove();
                }
            },
            closeAllActionRows(exceptCell = null) {
                document.querySelectorAll('.logo-cell.active').forEach(c => {
                    if (exceptCell && c === exceptCell) return;
                    c.classList.remove('active');
                    const ar = c.closest('tr').nextElementSibling;
                    if (ar && ar.classList.contains('action-row')) ar.remove();
                });
            },
            escape(str) {
                const d = document.createElement('div');
                d.textContent = str;
                return d.innerHTML;
            },
        };

        // Actions
        async function handleCreateProject() {
            UI.showWelcome('⏳ Creating project...');
            try {
                const r = await API.createProject();
                await refreshDataAndView(false);
                UI.showWelcome(r.message || '✅ Project created');
            } catch (e) { UI.showWelcome('❌ Create failed: ' + e.message); }
        }

        async function handleInstallConfirm(repo) {
            UI.showWelcome('⏳ Installing ' + repo.name + '...');
            try {
                await API.installRepos([repo.url]);
                State.installedUrls.add(normalizeRepoUrl(repo.url));
                recalcStateCounters();
                UI.updateHeader();
                UI.renderTable();
                UI.showWelcome('✅ Installed ' + repo.name);
                closeActionRow(repo.url);
                return true;
            } catch (e) { UI.showWelcome('❌ Install failed: ' + e.message); }
            return false;
        }

        async function handleDeleteConfirm(repo) {
            UI.showWelcome('⏳ Deleting ' + repo.name + '...');
            try {
                await API.deleteRepos([repo.name]);
                const url = normalizeRepoUrl(repo.url);
                State.installedUrls.delete(url);
                State.installedCount = State.installedUrls.size;
                if (repo.url.includes('NEW_PROJECTS')) {
                    removeLocalDescription(repo.name);
                    State.localDescriptions = readLocalDescriptions();
                    State.repos = State.repos.filter(r => !(r.name === repo.name && r.url === repo.url));
                }
                recalcStateCounters();
                UI.updateHeader();
                UI.renderTable();
                UI.showWelcome('✅ Deleted ' + repo.name);
                // Close action row after deletion
                closeActionRow(repo.url);
            } catch (e) { UI.showWelcome('❌ Delete failed: ' + e.message); }
        }

        async function handleAddToGithubConfirm(repo, visibility = 'public') {
            closeActionRow(repo.url);
            UI.showWelcome(`⏳ Creating ${visibility} GitHub repository for ${repo.name}...`);
            try {
                const sourceRepo = State.repos.find(r => r.name === repo.name && r.url === repo.url);
                const description = sourceRepo?.description || '';
                const r = await API.addToGithub(repo.name, description, visibility);
                removeLocalDescription(repo.name);
                State.localDescriptions = readLocalDescriptions();
                const repoUrl = String(r.repo || '').trim();
                const normalizedUrl = repoUrl
                    ? normalizeRepoUrl(repoUrl.startsWith('http') ? repoUrl : `https://github.com/${repoUrl}`)
                    : '';
                if (sourceRepo) {
                    sourceRepo.is_new_project = false;
                    sourceRepo.private = visibility === 'private';
                    sourceRepo.can_push = false;
                    if (normalizedUrl) sourceRepo.url = normalizedUrl;
                }
                if (normalizedUrl) State.installedUrls.add(normalizedUrl);
                recalcStateCounters();
                UI.updateHeader();
                UI.renderTable();
                UI.showWelcome(`✅ Added to GitHub (${visibility}): ` + (r.repo || repo.name));
            } catch (e) {
                UI.showWelcome('❌ Add to GitHub failed: ' + e.message);
            }
        }

        async function handleDeleteGithubConfirm(repo) {
            UI.showWelcome('⏳ Deleting from GitHub ' + repo.name + '...');
            try {
                await API.deleteGithubRepo(repo.name);
                State.repos = State.repos.filter(r => !(r.name === repo.name && r.url === repo.url));
                recalcStateCounters();
                UI.updateHeader();
                UI.renderTable();
                UI.showWelcome('✅ Deleted from GitHub ' + repo.name);
                closeActionRow(repo.url);
            } catch (e) {
                UI.showWelcome('❌ GitHub delete failed: ' + e.message);
            }
        }

        async function handlePushConfirm(repo, versionMode = 'use_existing') {
            closeActionRow(repo.url);
            setRepoCanPush(repo, false);
            UI.showWelcome('⏳ Updating VERSION.md and pushing ' + repo.name + '...');
            try {
                await API.pushRepo(repo.url, '', versionMode);
                UI.showWelcome('✅ Push completed for ' + repo.name);
            } catch (e) {
                setRepoCanPush(repo, true);
                UI.showWelcome('❌ Push failed: ' + e.message);
            }
        }

        function delay(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }

        function isTransientOpenError(err) {
            const msg = String(err?.message || err || '').toLowerCase();
            return (
                msg.includes('http 500')
                || msg.includes('internal server error')
                || msg.includes('failed to fetch')
                || msg.includes('networkerror')
                || msg.includes('network error')
                || msg.includes('aborterror')
            );
        }

        async function openWithRetry(openCall, retryDelayMs = 300) {
            try {
                return await openCall();
            } catch (firstErr) {
                if (!isTransientOpenError(firstErr)) throw firstErr;
                await delay(retryDelayMs);
                return await openCall();
            }
        }

        async function launchRepoFromUrlAction(repo, rowNo, isLocal) {
            if (!repo || !repo.url) return;
            if (isLocal) {
                try {
                    await openWithRetry(() => API.openFolder(repo.url));
                    UI.markLastUrlLaunch(rowNo);
                    UI.showWelcome('✅ Opened in VS Code');
                } catch (err) {
                    UI.showWelcome('❌ Open failed: ' + err.message);
                }
                return;
            }

            const isInstalled = State.isInstalled(repo);
            if (!isInstalled) {
                const ok = await handleInstallConfirm(repo);
                if (!ok) return;
            }
            try {
                await openWithRetry(() => API.openFolder(repo.url || repo.name));
                UI.markLastUrlLaunch(rowNo);
                UI.showWelcome('✅ Opened in VS Code');
            } catch (err) {
                UI.showWelcome('❌ Open failed: ' + err.message);
            }
        }

        async function launchNextFromLastOpened() {
            const next = State.getNextLaunchRepo();
            if (!next) {
                UI.showWelcome('❌ No projects available');
                return;
            }

            await launchRepoFromUrlAction(
                { name: next.name, url: next.url },
                Number(next.__rowNo),
                !!next.is_new_project
            );
        }

        function isHttpUrl(value = '') {
            return /^https?:\/\//i.test(String(value || '').trim());
        }

        function makeEditable(cell, name, url, endpoint) {
            const original = name;
            const input = document.createElement('input');
            input.type = 'text';
            input.value = original;
            input.className = 'rename-input';
            cell.textContent = '';
            cell.appendChild(input);
            input.focus();
            input.select();

            async function save() {
                const newName = input.value.trim();
                if (newName && newName !== original) {
                    try {
                        const fn = endpoint.includes('rename-github') ? 'renameGithub' : 'renameLocal';
                        await API[fn](original, newName);
                        const newUrl = url.replace(new RegExp(`${original.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`), newName);
                        if (fn === 'renameLocal') {
                            renameLocalDescription(original, newName);
                            State.localDescriptions = readLocalDescriptions();
                        }
                        const repoItem = State.repos.find(r => r.name === original);
                        if (repoItem) {
                            repoItem.name = newName;
                            repoItem.url = newUrl;
                        }
                        recalcStateCounters();
                        UI.updateHeader();
                        UI.renderTable();
                        UI.showWelcome('✅ Renamed to ' + newName);
                        closeActionRow(newUrl);
                    } catch (e) {
                        UI.showWelcome('❌ Rename failed: ' + e.message);
                        cell.textContent = original;
                    }
                } else { cell.textContent = original; }
            }
            input.addEventListener('blur', save);
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter') input.blur();
                else if (e.key === 'Escape') cell.textContent = original;
            });
        }

        function makeDescriptionEditable(cell, name, isLocal = false) {
            const original = cell.textContent || '';
            const input = document.createElement('input');
            input.type = 'text';
            input.value = original;
            input.className = 'rename-input';
            cell.textContent = '';
            cell.appendChild(input);
            input.focus();
            input.select();

            async function save() {
                const newDescription = input.value.trim();
                if (newDescription !== original) {
                    try {
                        const repoItem = State.repos.find(r => r.name === name);
                        if (isLocal) {
                            setLocalDescription(name, newDescription);
                            State.localDescriptions = readLocalDescriptions();
                        } else {
                            await API.updateDescription(name, newDescription);
                        }
                        if (repoItem) repoItem.description = newDescription;
                        UI.renderTable();
                        UI.showWelcome('✅ Description updated');
                    } catch (e) {
                        UI.showWelcome('❌ Description update failed: ' + e.message);
                        cell.textContent = original;
                    }
                } else {
                    cell.textContent = original;
                }
            }

            input.addEventListener('blur', save);
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter') input.blur();
                else if (e.key === 'Escape') cell.textContent = original;
            });
        }

        function closeActionRow(url) {
            const row = document.querySelector(`tr[data-url="${CSS.escape(url)}"]`);
            if (row) {
                const logoCell = row.querySelector('.logo-cell');
                if (logoCell) logoCell.classList.remove('active');
                const ar = row.nextElementSibling;
                if (ar && ar.classList.contains('action-row')) ar.remove();
            }
        }

        function setRepoCanPush(repo, canPush) {
            const value = !!canPush;
            const row = document.querySelector(`tr[data-url="${CSS.escape(repo.url)}"]`);
            if (row) {
                row.dataset.canPush = value ? 'true' : 'false';
                const logoCell = row.querySelector('.logo-cell');
                if (logoCell) logoCell.classList.toggle('has-unpushed', value);
            }
            const stateItem = State.repos.find(r => r.name === repo.name && r.url === repo.url);
            if (stateItem) stateItem.can_push = value;
            UI.patchActionRowForRepo(repo.url);
        }

        async function loadProjectScreenshots(actionRow, repo) {
            if (!actionRow || !actionRow.isConnected) return;
            const host = actionRow.querySelector('.screenshots-panel');
            if (!host) return;
            try {
                const data = await API.getProjectScreenshots(repo.url || repo.name || '');
                if (!actionRow.isConnected) return;
                const items = Array.isArray(data?.items) ? data.items : [];
                if (!items.length) {
                    host.innerHTML = '';
                    return;
                }
                host.innerHTML = `
                    <div class="screenshots-grid">
                        ${items.map(item => `
                            <button class="screenshot-item" type="button" data-preview-src="${UI.escape(item.src)}" data-preview-alt="${UI.escape(item.name || 'screenshot')}">
                                <img class="screenshot-thumb" src="${UI.escape(item.src)}" alt="${UI.escape(item.name || 'screenshot')}" loading="lazy">
                                <div class="screenshot-name">${UI.escape(item.name || '')}</div>
                            </button>
                        `).join('')}
                    </div>
                `;
            } catch {
                if (!actionRow.isConnected) return;
                host.innerHTML = '';
            }
        }

        function finishBootstrap(errorMessage = '') {
            if (errorMessage) {
                document.body.classList.add('app-error');
                const loader = document.getElementById('boot-loader');
                if (loader) loader.textContent = errorMessage;
                return;
            }
            document.body.classList.remove('app-error');
            document.body.classList.add('app-ready');
        }

        function mountTemplate(html) {
            const shell = document.getElementById('app-shell');
            if (!shell) return;
            shell.innerHTML = html;
        }

        function captureUiSnapshot() {
            const activeCell = document.querySelector('.logo-cell.active');
            return {
                activeUrl: activeCell?.dataset?.url || '',
                scrollY: window.scrollY || 0,
            };
        }

        function restoreUiSnapshot(snapshot) {
            if (!snapshot) return;
            const y = Number(snapshot.scrollY || 0);
            if (Number.isFinite(y)) window.scrollTo(0, y);
            if (!snapshot.activeUrl) return;
            const cell = document.querySelector(`.logo-cell[data-url="${CSS.escape(snapshot.activeUrl)}"]`);
            if (cell) UI.openActionRow(cell);
        }

        async function bootstrapApp({ remount = false, keepWelcome = false, skipDataReload = false } = {}) {
            if (remount) {
                const prevWelcome = keepWelcome && UI.el?.welcome ? UI.el.welcome.textContent : '';
                mountTemplate(appTemplate);
                if (prevWelcome) {
                    const nextWelcome = document.getElementById('welcome-text');
                    if (nextWelcome) nextWelcome.textContent = prevWelcome;
                }
            }

            if (appEventController) appEventController.abort();
            appEventController = new AbortController();
            const signal = appEventController.signal;

            ConfirmDialog.init(signal);
            ImagePreview.init(signal);
            UI.init();
            try {
                if (skipDataReload) {
                    UI.updateHeader();
                    UI.renderTable();
                } else {
                    await refreshDataAndView(false);
                }
                finishBootstrap();
                if (!keepWelcome) UI.showWelcome(UI.el.welcome.textContent || '');
            } catch (e) {
                finishBootstrap('Failed to load data');
                UI.showWelcome('❌ Init failed: ' + e.message);
                return;
            }

            document.getElementById('btn-create-new').addEventListener('click', async (e) => {
                e.preventDefault();
                await handleCreateProject();
            }, { signal });

            UI.el.lastUrl.addEventListener('click', async (e) => {
                e.preventDefault();
                await launchNextFromLastOpened();
            }, { signal });
            UI.el.clock?.addEventListener('click', (e) => e.preventDefault(), { signal });

            UI.el.welcome.addEventListener('click', () => UI.showWelcome('Добро пожаловать, Мастер'), { signal });
            UI.el.search.addEventListener('input', () => UI.renderTable(), { signal });
            UI.el.headers.forEach(header => {
                header.addEventListener('click', () => UI.setSort(header.dataset.sort), { signal });
            });

            document.addEventListener('click', (e) => {
                const cell = e.target.closest('.logo-cell, .name-cell, .description-cell');
                if (!cell) return;
                e.stopPropagation();
                const logoCell = cell.classList.contains('logo-cell')
                    ? cell
                    : cell.closest('tr')?.querySelector('.logo-cell');
                if (logoCell) UI.openActionRow(logoCell);
            }, { signal });

            document.addEventListener('click', (e) => {
                if (e.target.closest('.logo-cell, .name-cell, .description-cell') || e.target.closest('.action-row')) return;
                if (e.target.closest('#image-preview-overlay')) return;
                UI.closeAllActionRows();
            }, { signal });

            document.addEventListener('click', async (e) => {
                const link = e.target.closest('.url-link');
                if (link) {
                    e.preventDefault();
                    const row = link.closest('tr');
                    const repo = {
                        name: row ? row.dataset.name : '',
                        url: link.dataset.url
                    };
                    const rowNo = row ? Number(row.querySelector('.rownum-cell')?.textContent || 0) : 0;
                    await launchRepoFromUrlAction(repo, rowNo, link.dataset.isLocal === 'true');
                }
            }, { signal });

            document.addEventListener('click', (e) => {
                const toggleBtn = e.target.closest('[data-action="toggle-submenu"]');
                if (toggleBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    const wrap = toggleBtn.closest('.action-submenu-wrap');
                    const submenu = wrap ? wrap.querySelector('.action-submenu') : null;
                    if (!submenu) return;
                    const wasOpen = submenu.classList.contains('open');
                    document.querySelectorAll('.action-submenu.open').forEach(s => s.classList.remove('open'));
                    if (!wasOpen) submenu.classList.add('open');
                    return;
                }
                if (!e.target.closest('.action-submenu-wrap')) {
                    document.querySelectorAll('.action-submenu.open').forEach(s => s.classList.remove('open'));
                }
            }, { signal });

            document.addEventListener('click', async (e) => {
                const btn = e.target.closest('.action-btn');
                if (btn) {
                    e.preventDefault();
                    const { action, name: repoName, url: repoUrl } = btn.dataset;
                    if (action === 'toggle-submenu') return;
                    const repo = { name: repoName, url: repoUrl };
                    if (action === 'edit-name') {
                        const actionRow = btn.closest('tr.action-row');
                        const repoRow = actionRow ? actionRow.previousElementSibling : null;
                        if (!repoRow) return;
                        const cell = repoRow.querySelector('.name-cell');
                        if (!cell) return;
                        const endpoint = repoRow.dataset.isNew === 'true' ? '/api/rename' : '/api/rename-github';
                        makeEditable(cell, cell.dataset.repo, cell.dataset.url, endpoint);
                    }
                    else if (action === 'edit-description') {
                        const actionRow = btn.closest('tr.action-row');
                        const repoRow = actionRow ? actionRow.previousElementSibling : null;
                        if (!repoRow) return;
                        const cell = repoRow.querySelector('.description-cell');
                        if (!cell) return;
                        const isLocal = repoRow.dataset.isNew === 'true';
                        makeDescriptionEditable(cell, cell.dataset.repo, isLocal);
                    }
                    else if (action === 'add-to-github') {
                        const actionCell = btn.closest('.action-cell');
                        const visibilitySelect = actionCell ? actionCell.querySelector('.action-visibility') : null;
                        const vis = visibilitySelect && visibilitySelect.value === 'private' ? 'private' : 'public';
                        await handleAddToGithubConfirm(repo, vis);
                    }
                    else if (action === 'push') {
                        const actionCell = btn.closest('.action-cell');
                        const pushModeSelect = actionCell ? actionCell.querySelector('.action-push-mode') : null;
                        const pushMode = pushModeSelect ? String(pushModeSelect.value || 'use_existing') : 'use_existing';
                        await handlePushConfirm(repo, pushMode);
                    }
                    else if (action === 'open-vscode') {
                        const actionRow = btn.closest('tr.action-row');
                        const repoRow = actionRow ? actionRow.previousElementSibling : null;
                        const isLocal = repoRow ? repoRow.dataset.isNew === 'true' : false;
                        const rowNo = repoRow ? Number(repoRow.querySelector('.rownum-cell')?.textContent || 0) : 0;
                        await launchRepoFromUrlAction(repo, rowNo, isLocal);
                        closeActionRow(repo.url);
                    }
                    else if (action === 'open-folder') {
                        try {
                            await openWithRetry(() => API.openFolderExplorer(repo.url || repo.name));
                            UI.showWelcome('✅ Folder opened');
                            closeActionRow(repo.url);
                        } catch (e) {
                            UI.showWelcome('❌ Open failed: ' + e.message);
                        }
                    }
                    else if (action === 'open-repository') {
                        if (!isHttpUrl(repo.url)) {
                            UI.showWelcome('❌ GitHub link not found');
                            return;
                        }
                        window.open(repo.url, '_blank', 'noopener');
                        UI.showWelcome('✅ Repository opened');
                        closeActionRow(repo.url);
                    }
                    else if (action === 'delete') {
                        const ok = await ConfirmDialog.open(`Delete "${repoName}"?`, { confirmText: 'Delete', danger: true });
                        if (ok) await handleDeleteConfirm(repo);
                    }
                    else if (action === 'delete-github') {
                        const ok = await ConfirmDialog.open(`Delete "${repoName}" from GitHub?`, { confirmText: 'Delete', danger: true });
                        if (ok) await handleDeleteGithubConfirm(repo);
                    }
                }
            }, { signal });
        }

        async function startup() {
            mountTemplate(appTemplate);
            const skipDataReload = isHotModuleReload && restoreStateSnapshot(hotState);
            await bootstrapApp({ skipDataReload, keepWelcome: skipDataReload });
            if (skipDataReload) restoreUiSnapshot(hotSnapshot);
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', startup, { once: true });
        } else {
            startup();
        }

        if (import.meta.hot) {
            import.meta.hot.accept(() => {});
            import.meta.hot.accept('./app.template.html?raw', async (mod) => {
                const snap = captureUiSnapshot();
                appTemplate = mod?.default || appTemplate;
                mountTemplate(appTemplate);
                await bootstrapApp({ remount: false, keepWelcome: true, skipDataReload: true });
                restoreUiSnapshot(snap);
            });
            import.meta.hot.accept('./ui.templates.js', async (mod) => {
                const snap = captureUiSnapshot();
                if (mod) templateApi = mod;
                if (UI.el?.tbody) UI.renderTable();
                restoreUiSnapshot(snap);
            });
            import.meta.hot.dispose(() => {
                import.meta.hot.data.wasMounted = true;
                import.meta.hot.data.snapshot = captureUiSnapshot();
                import.meta.hot.data.state = captureStateSnapshot();
                if (appEventController) appEventController.abort();
                if (UI.welcomeTimer) {
                    clearTimeout(UI.welcomeTimer);
                    UI.welcomeTimer = null;
                }
            });
        }
