// @ts-nocheck
const vscode = acquireVsCodeApi();

function renderTrace(traceData, symbol) {
  const container = document.getElementById('content');
  container.innerHTML = '';

  if (!traceData) {
    container.innerHTML = '<p>No trace data available</p>';
    return;
  }

  const h1 = document.createElement('h1');
  h1.textContent = `Trace: ${symbol}`;
  container.appendChild(h1);

  const pre = document.createElement('pre');
  pre.textContent = JSON.stringify(traceData, null, 2);
  container.appendChild(pre);
}

window.addEventListener('message', (event) => {
  const message = event.data;
  if (message.type === 'update') {
    renderTrace(message.data, message.symbol);
  }
});
