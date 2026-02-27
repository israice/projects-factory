export function renderRepoRow({
  repo,
  created,
  isNew,
  logoClass,
  logo,
  escape
}) {
  return `
    <td class="rownum-cell">${repo.__rowNo || ""}</td>
    <td class="${logoClass}" data-repo="${escape(repo.name)}" data-url="${escape(repo.url)}"><span class="logo-icon">📦</span></td>
    <td class="name-cell" data-repo="${escape(repo.name)}" data-url="${escape(repo.url)}">${escape(repo.name)}</td>
    <td class="description-cell" data-repo="${escape(repo.name)}" data-url="${escape(repo.url)}">${escape(repo.description || "")}</td>
    <td class="url-cell">
      <a href="${escape(repo.url)}" class="url-link" data-url="${escape(repo.url)}" data-is-local="${isNew}">${logo}</a>
    </td>
    <td class="started-cell"><span class="date-badge">${created.date}<br>${created.time}</span></td>
  `;
}

export function renderActionButtons({
  isNew,
  installed,
  canPush,
  name,
  url,
  isHttpUrl,
  escape
}) {
  if (isNew) {
    const pushMode = canPush
      ? `<select class="action-visibility action-push-mode" data-action="push-mode">
          <option value="use_existing" selected>Use Existing</option>
          <option value="generate_version">Generate Version</option>
        </select>`
      : "";
    const pushBtn = canPush
      ? `<button class="action-btn" data-action="push" data-name="${escape(name)}" data-url="${escape(url)}">⬆️ Push</button>`
      : "";
    const repoBtn = isHttpUrl(url)
      ? `<button class="action-btn" data-action="open-repository" data-name="${escape(name)}" data-url="${escape(url)}">🌐 Repository</button>`
      : "";
    return `
      <div class="action-submenu-wrap">
        <button class="action-btn" data-action="toggle-submenu" data-submenu="local"><svg width="14" height="14" viewBox="0 0 16 16" fill="#2196F3" style="vertical-align:middle"><path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v10.5C0 14.216.784 15 1.75 15h12.5A1.75 1.75 0 0 0 16 13.25v-8.5A1.75 1.75 0 0 0 14.25 3H7.5a.25.25 0 0 1-.2-.1l-.9-1.2C6.07 1.26 5.55 1 5 1H1.75z"/></svg> Local</button>
        <div class="action-submenu" data-submenu-id="local">
          <button class="action-btn" data-action="open-folder" data-name="${escape(name)}" data-url="${escape(url)}">📂 Folder</button>
          ${pushMode}
          ${pushBtn}
          <select class="action-visibility" data-action="visibility">
            <option value="public" selected>Public</option>
            <option value="private">Private</option>
          </select>
          <button class="action-btn" data-action="add-to-github" data-name="${escape(name)}" data-url="${escape(url)}">☁️ Add to GitHub</button>
          <button class="action-btn" data-action="delete" data-name="${escape(name)}" data-url="${escape(url)}">🗑️ Local Delete</button>
        </div>
      </div>
    `;
  }

  if (installed) {
    const pushMode = canPush
      ? `<select class="action-visibility action-push-mode" data-action="push-mode">
          <option value="use_existing" selected>Use Existing</option>
          <option value="generate_version">Generate Version</option>
        </select>`
      : "";
    const pushBtn = canPush
      ? `<button class="action-btn" data-action="push" data-name="${escape(name)}" data-url="${escape(url)}">⬆️ Push</button>`
      : "";
    const repoBtn = isHttpUrl(url)
      ? `<button class="action-btn" data-action="open-repository" data-name="${escape(name)}" data-url="${escape(url)}">🌐 Repository</button>`
      : "";
    return `
      <div class="action-submenu-wrap">
        <button class="action-btn" data-action="toggle-submenu" data-submenu="local"><svg width="14" height="14" viewBox="0 0 16 16" fill="#2196F3" style="vertical-align:middle"><path d="M1.75 1A1.75 1.75 0 0 0 0 2.75v10.5C0 14.216.784 15 1.75 15h12.5A1.75 1.75 0 0 0 16 13.25v-8.5A1.75 1.75 0 0 0 14.25 3H7.5a.25.25 0 0 1-.2-.1l-.9-1.2C6.07 1.26 5.55 1 5 1H1.75z"/></svg> Local</button>
        <div class="action-submenu" data-submenu-id="local">
          <button class="action-btn" data-action="open-folder" data-name="${escape(name)}" data-url="${escape(url)}">📂 Folder</button>
          ${pushMode}
          ${pushBtn}
          <button class="action-btn" data-action="delete" data-name="${escape(name)}" data-url="${escape(url)}">🗑️ Local Delete</button>
        </div>
      </div>
      <div class="action-submenu-wrap">
        <button class="action-btn" data-action="toggle-submenu" data-submenu="github"><svg width="14" height="14" viewBox="0 0 16 16" fill="#fff" style="vertical-align:middle"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg> Github</button>
        <div class="action-submenu" data-submenu-id="github">
          ${repoBtn}
          <button class="action-btn" data-action="delete-github" data-name="${escape(name)}" data-url="${escape(url)}">☁️ Delete Repository</button>
        </div>
      </div>
    `;
  }

  return "";
}

export function renderActionRowCell(buttons) {
  return `<td colspan="6" class="action-cell">${buttons}<div class="screenshots-panel"></div></td>`;
}
