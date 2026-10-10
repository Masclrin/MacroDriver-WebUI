const collapsedByView = new Map();

function ensureCollapsedSet(viewId) {
  if (!collapsedByView.has(viewId)) {
    collapsedByView.set(viewId, new Set());
  }
  return collapsedByView.get(viewId);
}

function normalizeTree(tree) {
  if (!tree || typeof tree !== 'object') {
    return { name: '宏', path: '宏', folders: [], files: [] };
  }
  return {
    name: String(tree.name || '宏'),
    path: String(tree.path || '宏'),
    folders: Array.isArray(tree.folders) ? tree.folders : [],
    files: Array.isArray(tree.files) ? tree.files : [],
  };
}

function buildRows(tree, depth, collapsedSet, rows) {
  const folders = [...tree.folders].sort((a, b) => String(a.name).localeCompare(String(b.name), 'zh-Hans-CN'));
  const files = [...tree.files].sort((a, b) => String(a.path).localeCompare(String(b.path), 'zh-Hans-CN'));

  folders.forEach((folder) => {
    const folderPath = String(folder.path || '');
    const collapsed = collapsedSet.has(folderPath);
    rows.push({
      kind: 'folder',
      name: String(folder.name || ''),
      path: folderPath,
      depth,
      collapsed,
    });

    if (!collapsed) {
      buildRows(normalizeTree(folder), depth + 1, collapsedSet, rows);
    }
  });

  files.forEach((file) => {
    rows.push({
      kind: 'file',
      name: String(file.name || ''),
      path: String(file.path || ''),
      depth,
    });
  });
}

function createRowIndent(depth) {
  const indent = document.createElement('span');
  indent.className = 'macro-tree-indent';
  indent.style.width = `${Math.max(0, depth) * 14}px`;
  return indent;
}

export function renderMacroTreeList({
  container,
  tree,
  viewId,
  selectedPath,
  openedPath,
  onSelect,
  onFill,
}) {
  if (!container) return;

  const safeTree = normalizeTree(tree);
  const collapsedSet = ensureCollapsedSet(viewId);

  const rows = [];
  buildRows(safeTree, 0, collapsedSet, rows);

  container.innerHTML = '';

  rows.forEach((row) => {
    const li = document.createElement('li');
    li.classList.add('macro-tree-row');
    li.classList.add(`macro-tree-${row.kind}`);
    li.dataset.path = row.path;

    const content = document.createElement('div');
    content.className = 'macro-tree-content';

    content.appendChild(createRowIndent(row.depth));

    if (row.kind === 'folder') {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'macro-tree-toggle';
      toggle.textContent = row.collapsed ? '▶' : '▼';
      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        if (collapsedSet.has(row.path)) {
          collapsedSet.delete(row.path);
        } else {
          collapsedSet.add(row.path);
        }
        renderMacroTreeList({
          container,
          tree: safeTree,
          viewId,
          selectedPath,
          openedPath,
          onSelect,
          onFill,
        });
      });

      const name = document.createElement('span');
      name.className = 'macro-tree-name';
      name.textContent = row.name;

      content.appendChild(toggle);
      content.appendChild(name);
      li.appendChild(content);
      container.appendChild(li);
      return;
    }

    const dot = document.createElement('span');
    dot.className = 'macro-tree-file-dot';
    dot.textContent = '•';
    content.appendChild(dot);

    const name = document.createElement('span');
    name.className = 'macro-tree-name';
    name.textContent = row.path;
    content.appendChild(name);

    li.classList.toggle('active', row.path === selectedPath);
    li.classList.toggle('opened', row.path === openedPath);
    li.draggable = true;

    li.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/macro-path', row.path);
      e.dataTransfer.setData('text/plain', row.path);
      e.dataTransfer.effectAllowed = 'copy';
    });

    li.addEventListener('click', () => {
      if (typeof onSelect === 'function') {
        onSelect(row.path);
      }
      if (typeof onFill === 'function') {
        onFill(row.path);
      }
    });

    li.appendChild(content);
    container.appendChild(li);
  });
}
