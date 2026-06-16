// @ts-nocheck
const vscode = acquireVsCodeApi();

function renderImpact(impactData, symbol) {
  const container = document.getElementById('content');
  container.innerHTML = '';

  if (!impactData) {
    container.innerHTML = '<p>No impact data available</p>';
    return;
  }

  const h1 = document.createElement('h1');
  h1.textContent = `Impact: ${symbol}`;
  container.appendChild(h1);

  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(impactData, null, 2);
  container.appendChild(pre);
}

window.addEventListener('message', (event) => {
  const message = event.data;
  if (message.type === 'update') {
    renderImpact(message.data, message.symbol);
  }
});
