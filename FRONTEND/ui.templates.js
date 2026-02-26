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
      <button class="action-btn" data-action="open-folder" data-name="${escape(name)}" data-url="${escape(url)}">📂 Folder</button>
      ${repoBtn}
      ${pushMode}
      ${pushBtn}
      <select class="action-visibility" data-action="visibility">
        <option value="public" selected>Public</option>
        <option value="private">Private</option>
      </select>
      <button class="action-btn" data-action="add-to-github" data-name="${escape(name)}" data-url="${escape(url)}">☁️ Add to GitHub</button>
      <button class="action-btn" data-action="delete" data-name="${escape(name)}" data-url="${escape(url)}">🗑️ Local Delete</button>
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
      <button class="action-btn" data-action="open-folder" data-name="${escape(name)}" data-url="${escape(url)}">📂 Folder</button>
      ${repoBtn}
      ${pushMode}
      ${pushBtn}
      <button class="action-btn" data-action="delete" data-name="${escape(name)}" data-url="${escape(url)}">🗑️ Local Delete</button>
      <button class="action-btn" data-action="delete-github" data-name="${escape(name)}" data-url="${escape(url)}">☁️ Delete Repository</button>
    `;
  }

  return "";
}

export function renderActionRowCell(buttons) {
  return `<td colspan="6" class="action-cell">${buttons}<div class="screenshots-panel"><div class="screenshots-empty">Loading screenshots...</div></div></td>`;
}
