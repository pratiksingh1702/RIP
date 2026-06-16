// @ts-nocheck
const vscode = acquireVsCodeApi();

function renderGraph(graphData) {
  const container = document.getElementById('graph');
  container.innerHTML = '';

  if (!graphData || !graphData.services || graphData.services.length === 0) {
    container.innerHTML = '<p>No dependency graph data available</p>';
    return;
  }

  const width = container.clientWidth;
  const height = container.clientHeight || 600;

  const svg = d3.select(container)
    .append('svg')
    .attr('width', width)
    .attr('height', height);

  const nodes = graphData.services.map((s, i) => ({
    id: s.name,
    label: s.name,
    x: Math.random() * width,
    y: Math.random() * height,
  }));

  const links = graphData.dependencies.map(d => ({
    source: d.from,
    target: d.to,
  }));

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(100))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2));

  const link = svg.append('g')
    .selectAll('line')
    .data(links)
    .enter().append('line')
    .attr('stroke', '#999')
    .attr('stroke-opacity', 0.6)
    .attr('stroke-width', 2);

  const node = svg.append('g')
    .selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', 10)
    .attr('fill', '#69b3a2')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended));

  const label = svg.append('g')
    .selectAll('text')
    .data(nodes)
    .enter().append('text')
    .attr('dy', -15)
    .attr('text-anchor', 'middle')
    .text(d => d.label)
    .attr('font-size', '12px')
    .attr('fill', '#333');

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y);

    label
      .attr('x', d => d.x)
      .attr('y', d => d.y);
  });

  function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }

  function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
  }

  function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
}

window.addEventListener('message', (event) => {
  const message = event.data;
  if (message.type === 'update') {
    renderGraph(message.data);
  }
});

document.addEventListener('DOMContentLoaded', () => {
  renderGraph(null);
});
