const vscode = acquireVsCodeApi();

const messagesEl = document.getElementById('messages');
const form = document.getElementById('composer');
const queryEl = document.getElementById('query');
const commandEl = document.getElementById('command');
const resetButton = document.getElementById('resetButton');
const refreshButton = document.getElementById('refreshButton');
const modeValue = document.getElementById('modeValue');
const serverValue = document.getElementById('serverValue');
const indexValue = document.getElementById('indexValue');
const workspaceValue = document.getElementById('workspaceValue');
const focusValue = document.getElementById('focusValue');
const commandValue = document.getElementById('commandValue');
const queryValue = document.getElementById('queryValue');
const promptButtons = document.querySelectorAll('[data-prompt]');

if (window.mermaid) {
  window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'base' });
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  submitQuery();
});

queryEl.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    submitQuery();
  }
});

queryEl.addEventListener('input', () => {
  queryEl.style.height = 'auto';
  queryEl.style.height = `${Math.min(queryEl.scrollHeight, 150)}px`;
});

resetButton.addEventListener('click', () => {
  vscode.postMessage({ type: 'reset' });
});

refreshButton.addEventListener('click', () => {
  vscode.postMessage({ type: 'refreshStatus' });
});

promptButtons.forEach((button) => {
  button.addEventListener('click', () => submitQuery(button.dataset.prompt));
});

window.addEventListener('message', (event) => {
  if (event.data.type === 'messages') {
    render(event.data.messages || [], event.data.context || {}, event.data.status || {});
  }
});

vscode.postMessage({ type: 'ready' });

function submitQuery(value) {
  const query = (value || queryEl.value).trim();
  if (!query) {
    return;
  }
  vscode.postMessage({ type: 'query', query, command: commandEl.value });
  queryEl.value = '';
  queryEl.style.height = 'auto';
}

function render(messages, context, status) {
  modeValue.textContent = status.mode || 'CLI first';
  serverValue.textContent = status.server || 'optional';
  indexValue.textContent = status.indexed || 'CLI fallback';
  workspaceValue.textContent = status.workspace || 'workspace';
  focusValue.textContent = context.lastTarget || context.lastExplainedSymbol || 'No active symbol';
  commandValue.textContent = context.lastCommand || 'none';
  queryValue.textContent = context.lastQuery || 'none';
  messagesEl.innerHTML = '';
  for (const message of messages) {
    messagesEl.appendChild(renderMessage(message));
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderMessage(message) {
  const wrapper = el('article', `message ${message.role}`);
  wrapper.dataset.time = formatTime(message.timestamp);
  const bubble = el('div', 'bubble');
  for (const block of message.content || []) {
    bubble.appendChild(renderBlock(block, message.role));
  }
  wrapper.appendChild(bubble);
  return wrapper;
}

function renderBlock(block, role) {
  if (role === 'user') {
    return textNode(block.data, 'user-text');
  }

  const container = el('section', `block ${block.type || 'text'}-block`);
  if (block.type === 'status' && block.title && /run|running/i.test(block.title)) {
    container.classList.add('running-block');
  }
  if (block.title) {
    const head = el('div', 'block-head');
    const title = el('div', 'block-title');
    title.textContent = block.title;
    head.appendChild(title);
    if (block.type !== 'status') {
      head.appendChild(copyButton(serializableText(block.data)));
    }
    container.appendChild(head);
  }

  switch (block.type) {
    case 'status':
      container.appendChild(renderStatus(block.data));
      break;
    case 'table':
      container.appendChild(renderTable(block.data));
      break;
    case 'code':
      container.appendChild(renderCode(block.data, block.language || 'text'));
      break;
    case 'mermaid':
      container.appendChild(renderMermaid(block.data));
      break;
    case 'tree':
      container.appendChild(renderTree(block.data));
      break;
    case 'suggestion':
      container.appendChild(renderSuggestions(block.data));
      break;
    case 'error':
      container.appendChild(textNode(block.data, 'error'));
      break;
    default:
      if (/impact summary/i.test(block.title || '')) {
        container.appendChild(renderImpactSummary(block.data));
      } else {
        container.appendChild(textNode(block.data));
      }
      break;
  }
  return container;
}

function renderStatus(data) {
  const status = el('div', 'status-grid');
  for (const [key, value] of Object.entries(data || {})) {
    if (value === undefined || value === null || value === '') {
      continue;
    }
    const pill = el('span', 'pill');
    pill.textContent = `${key}: ${formatValue(value)}`;
    status.appendChild(pill);
  }
  return status;
}

function renderTable(data) {
  const rows = Array.isArray(data) ? data : [];
  const wrap = el('div', 'table-wrap');
  if (rows.length === 0) {
    wrap.appendChild(textNode('No rows returned.'));
    return wrap;
  }

  const normalized = rows.map((row) =>
    typeof row === 'object' && row !== null ? row : { value: row }
  );
  const headers = [...new Set(normalized.flatMap((row) => Object.keys(row)))].slice(0, 8);
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const tr = document.createElement('tr');
  for (const header of headers) {
    const th = document.createElement('th');
    th.textContent = header;
    tr.appendChild(th);
  }
  thead.appendChild(tr);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const row of normalized.slice(0, 80)) {
    const bodyRow = document.createElement('tr');
    for (const header of headers) {
      const td = document.createElement('td');
      td.textContent = formatValue(row[header]);
      bodyRow.appendChild(td);
    }
    tbody.appendChild(bodyRow);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  return wrap;
}

function renderCode(data, language) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  if (language === 'shell' || language === 'terminal') {
    return renderTerminal(text);
  }
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.textContent = text;
  pre.appendChild(code);
  return pre;
}

function renderTree(data) {
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  const pre = document.createElement('pre');
  const code = document.createElement('code');
  code.textContent = text;
  pre.appendChild(code);
  return pre;
}

function renderImpactSummary(data) {
  const text = typeof data === 'string' ? data : String(data || '');
  const pairs = Object.fromEntries(
    text
      .split(/\r?\n/)
      .map((line) => line.split(':').map((part) => part.trim()))
      .filter((parts) => parts.length >= 2 && parts[0])
      .map(([key, ...rest]) => [key.toLowerCase(), rest.join(':')])
  );
  const cards = [
    ['Used in', pairs['affected files'] || '0', 'files'],
    ['Watched by', pairs['affected apis'] || '0', 'APIs'],
    ['Affects', pairs['affected apis'] || '0', 'symbols'],
    ['Risk level', pairs.risk || 'unknown', ''],
  ];
  const grid = el('div', 'impact-grid');
  for (const [label, value, unit] of cards) {
    const card = el('div', 'impact-card');
    const labelNode = el('span', 'impact-label');
    labelNode.textContent = label;
    const valueNode = el('strong', label === 'Risk level' ? 'risk-value' : '');
    valueNode.textContent = value;
    const unitNode = el('span', 'impact-unit');
    unitNode.textContent = unit;
    card.append(labelNode, valueNode, unitNode);
    grid.appendChild(card);
  }
  return grid;
}

function renderTerminal(text) {
  const terminal = el('div', 'terminal');
  text.split(/\r?\n/).forEach((line, index) => {
    const row = el('div', `terminal-line ${line.trim().startsWith('$') ? 'prompt' : ''}`);
    row.style.animationDelay = `${index * 70}ms`;
    row.textContent = line;
    terminal.appendChild(row);
  });
  return terminal;
}

function renderMermaid(data) {
  const box = el('div', 'mermaid-box');
  const source = String(data || '').replace(/^```mermaid\s*/i, '').replace(/```\s*$/i, '').trim();
  if (!window.mermaid || !source) {
    box.appendChild(renderCode(source, 'mermaid'));
    return box;
  }
  const target = document.createElement('div');
  box.appendChild(target);
  const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.mermaid
    .render(id, source)
    .then(({ svg }) => {
      target.innerHTML = svg;
    })
    .catch(() => {
      target.replaceWith(renderCode(source, 'mermaid'));
    });
  return box;
}

function renderSuggestions(data) {
  const list = el('div', 'suggestions');
  const suggestions = Array.isArray(data) ? data : [];
  for (const suggestion of suggestions) {
    const button = el('button', 'suggestion');
    button.type = 'button';
    button.textContent = suggestion;
    button.addEventListener('click', () => submitQuery(suggestion));
    list.appendChild(button);
  }
  return list;
}

function copyButton(text) {
  const button = el('button', 'copy-button');
  button.type = 'button';
  button.textContent = 'Copy';
  button.addEventListener('click', async () => {
    await navigator.clipboard.writeText(text);
    button.textContent = 'Copied';
    setTimeout(() => {
      button.textContent = 'Copy';
    }, 1200);
  });
  return button;
}

function textNode(value, className = 'text-block') {
  const node = el('div', className);
  node.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return node;
}

function el(tag, className) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  return node;
}

function formatValue(value) {
  if (value === undefined || value === null) {
    return '';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

function serializableText(value) {
  return typeof value === 'string' ? value : JSON.stringify(value, null, 2);
}

function formatTime(timestamp) {
  if (!timestamp) {
    return '';
  }
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(
    new Date(timestamp)
  );
}
