// HackTree frontend: renders the tree returned by the Python API with D3.
const RISK_LABELS = { low: "Bajo", medium: "Medio", high: "Alto" };
const RISK_COLORS = { low: "#3f8f6b", medium: "#d89b2b", high: "#c0453a" };
const GATE_LABELS = { AND: "Y", OR: "O" };
const GATE_TEXT = {
  AND: "Se necesitan todas las condiciones",
  OR: "Basta con una de las condiciones",
};

const state = {
  treeData: null,
  index: new Map(),   // id -> { data, parentId }
  collapsed: new Set(),
  selectedId: null,
  visited: new Set(),
  matches: new Set(),
  busy: false,
};

const svg = d3.select("#tree");
const viewport = svg.append("g");
const linkLayer = viewport.append("g");
const nodeLayer = viewport.append("g");
const zoom = d3.zoom().scaleExtent([0.3, 2]).on("zoom", (e) => viewport.attr("transform", e.transform));
svg.call(zoom).on("dblclick.zoom", null);

const percent = (p) => `${Math.round(p * 100)}%`;
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`Error ${response.status}`);
  return response.json();
}

function showError() {
  alert("No se pudo comunicar con el servidor. Verifica que esté en ejecución e inténtalo de nuevo.");
}

function indexTree(data, parentId = null) {
  state.index.set(data.id, { data, parentId });
  data.children.forEach((child) => indexTree(child, data.id));
}

function allNodes() { return [...state.index.values()].map((entry) => entry.data); }

function wrapText(text, max = 30) {
  const lines = [];
  let line = "";
  text.split(" ").forEach((word) => {
    if ((line + " " + word).trim().length > max && line) { lines.push(line); line = word; }
    else line = (line + " " + word).trim();
  });
  if (line) lines.push(line);
  return lines.slice(0, 3);
}

function render() {
  const root = d3.hierarchy(state.treeData, (d) => (state.collapsed.has(d.id) ? null : d.children));
  d3.tree().nodeSize([58, 300])(root);

  linkLayer.selectAll("path").data(root.links(), (d) => d.target.data.id).join("path")
    .attr("class", (d) => `link ${d.source.data.gate === "AND" ? "and" : ""}`)
    .attr("d", d3.linkHorizontal().x((d) => d.y).y((d) => d.x));

  const nodes = nodeLayer.selectAll("g.node").data(root.descendants(), (d) => d.data.id)
    .join((enter) => {
      const g = enter.append("g").attr("class", "node").attr("tabindex", 0).attr("role", "button");
      g.append("circle").attr("class", "ring").attr("r", 17);
      g.append("circle").attr("class", "body").attr("r", 13);
      g.append("text").attr("class", "gate-text").attr("dy", "0.35em");
      g.append("text").attr("class", "label");
      g.append("text").attr("class", "meta").attr("y", 30);
      return g;
    });

  nodes.attr("transform", (d) => `translate(${d.y},${d.x})`)
    .attr("class", (d) => ["node",
      state.selectedId === d.data.id ? "selected" : "",
      state.visited.has(d.data.id) ? "visited" : "",
      state.matches.has(d.data.id) ? "match" : ""].join(" "))
    .attr("aria-label", (d) => `${d.data.label}, riesgo ${RISK_LABELS[d.data.risk_level]}`)
    .on("click", (_, d) => onNodeClick(d.data))
    .on("keydown", (e, d) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onNodeClick(d.data); } });

  nodes.select("circle.body").attr("fill", (d) => RISK_COLORS[d.data.risk_level]);
  nodes.select("text.gate-text").text((d) => (d.data.gate ? GATE_LABELS[d.data.gate] : ""));
  nodes.select("text.meta").text((d) => {
    const hidden = d.data.children.length && state.collapsed.has(d.data.id);
    return `${percent(d.data.probability)}${hidden ? "  ▸ expandir" : ""}`;
  });
  nodes.select("text.label").each(function (d) {
    const lines = wrapText(d.data.label);
    const text = d3.select(this).attr("x", -4).attr("y", -20 - (lines.length - 1) * 14);
    text.selectAll("tspan").data(lines).join("tspan").attr("x", -4).attr("dy", (_, i) => (i === 0 ? 0 : 14)).text((l) => l);
  });
}

function centerView() {
  const { width, height } = svg.node().getBoundingClientRect();
  svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity.translate(60, height / 2).scale(0.9));
}

function onNodeClick(data) {
  if (data.children.length) {
    if (state.collapsed.has(data.id)) state.collapsed.delete(data.id);
    else state.collapsed.add(data.id);
  }
  select(data.id);
}

async function select(id) {
  state.selectedId = id;
  render();
  await showDetails(id);
}

function collectMitigations(data) {
  const found = [];
  const walk = (node) => {
    node.mitigations.forEach((m) => found.push({ ...m, where: node.label }));
    node.children.forEach(walk);
  };
  walk(data);
  return found;
}

async function showDetails(id) {
  const data = state.index.get(id).data;
  let path = [];
  try { path = (await api(`/api/nodes/${id}/path`)).path; } catch { showError(); }
  const mitigations = collectMitigations(data);
  const panel = document.getElementById("panel");

  panel.innerHTML = `
    <p class="path">${path.map((n) => escapeHtml(n.label)).join(" › ")}</p>
    <h2>${escapeHtml(data.label)}</h2>
    <p>
      <span class="badge ${data.risk_level}">Riesgo ${RISK_LABELS[data.risk_level]}</span>
      ${data.gate ? `<span class="badge gate">${GATE_LABELS[data.gate]}</span><span class="muted">${GATE_TEXT[data.gate]}</span>` : '<span class="muted">Escenario de ataque específico</span>'}
    </p>
    <p>${escapeHtml(data.description)}</p>
    <h3>Probabilidad: ${percent(data.probability)} <span class="muted">(sin defensas: ${percent(data.baseline_probability)})</span></h3>
    <div class="bar" aria-hidden="true"><span class="base" style="width:${data.baseline_probability * 100}%"></span><span class="now" style="width:${data.probability * 100}%"></span></div>
    <p class="muted">Impacto: ${data.impact} de 10 · Puntaje de riesgo: ${data.risk} de 10</p>
    <h3>${mitigations.length ? "Medidas defensivas" : "Esta rama no tiene medidas defensivas directas"}</h3>
    ${mitigations.map((m) => `
      <label class="mit">
        <input type="checkbox" data-id="${escapeHtml(m.id)}" ${m.active ? "checked" : ""}>
        <span>${escapeHtml(m.name)} <strong>(−${Math.round(m.effectiveness * 100)}%)</strong></span>
        <small>${escapeHtml(m.description)}</small>
        <small class="where">Protege contra: ${escapeHtml(m.where)}</small>
      </label>`).join("")}`;

  panel.querySelectorAll(".mit input").forEach((box) =>
    box.addEventListener("change", () => toggleMitigation(box.dataset.id)));
}

function showOverview(stats) {
  if (state.selectedId) return;
  document.getElementById("panel").innerHTML = `
    <h2>Cómo usar HackTree</h2>
    <p>Haz clic en un nodo para ver su detalle y expandir o contraer sus ramas. Arrastra el lienzo para moverte y usa la rueda del ratón para acercar.</p>
    <p>Activa medidas defensivas en el panel y observa cómo baja la probabilidad de compromiso.</p>
    <h3>Amenazas con mayor riesgo</h3>
    <ol class="threats">${stats.top_threats.map((t) =>
      `<li><button data-id="${escapeHtml(t.id)}">${escapeHtml(t.label)}</button> <span class="muted">(${t.risk} de 10)</span></li>`).join("")}</ol>`;
  document.querySelectorAll(".threats button").forEach((b) => b.addEventListener("click", () => focusNode(b.dataset.id)));
}

function updateStats(stats) {
  document.getElementById("stat-current").textContent = percent(stats.current_probability);
  document.getElementById("stat-before").textContent =
    stats.current_probability !== stats.baseline_probability ? percent(stats.baseline_probability) : "";
  document.getElementById("stat-nodes").textContent = stats.total_nodes;
  document.getElementById("stat-leaves").textContent = stats.leaf_nodes;
  document.getElementById("stat-height").textContent = stats.height;
  document.getElementById("stat-mitigations").textContent = `${stats.active_mitigations} de ${stats.total_mitigations}`;
}

async function loadAll() {
  const [tree, stats] = await Promise.all([api("/api/tree"), api("/api/stats")]);
  state.treeData = tree;
  state.index.clear();
  indexTree(tree);
  updateStats(stats);
  return stats;
}

async function toggleMitigation(id) {
  try {
    await api(`/api/mitigations/${id}/toggle`, { method: "POST" });
    await loadAll();
    render();
    if (state.selectedId) await showDetails(state.selectedId);
  } catch { showError(); }
}

function ancestorsOf(id) {
  const ids = [];
  let parent = state.index.get(id).parentId;
  while (parent) { ids.push(parent); parent = state.index.get(parent).parentId; }
  return ids;
}

function focusNode(id) {
  ancestorsOf(id).forEach((a) => state.collapsed.delete(a));
  select(id);
}

function collapseDefault() {
  state.collapsed.clear();
  allNodes().filter((n) => n.depth === 1 && n.children.length).forEach((n) => state.collapsed.add(n.id));
}

async function runTraversal(order) {
  if (state.busy) return;
  state.busy = true;
  try {
    const { nodes } = await api(`/api/traversal?order=${order}`);
    state.collapsed.clear();
    state.visited.clear();
    render();
    const log = document.getElementById("traversal-log");
    log.hidden = false;
    const title = order === "dfs" ? "Recorrido en profundidad" : "Recorrido en anchura";
    for (let i = 0; i < nodes.length; i++) {
      state.visited.add(nodes[i].id);
      render();
      log.textContent = `${title}: ${i + 1}. ${nodes.slice(0, i + 1).map((n) => n.label).slice(-3).join(" → ")}`;
      await new Promise((r) => setTimeout(r, 380));
    }
    log.textContent = `${title} completo: se visitaron ${nodes.length} nodos.`;
  } catch { showError(); }
  state.busy = false;
}

async function search(query) {
  try {
    const { matches } = await api(`/api/search?q=${encodeURIComponent(query)}`);
    state.matches = new Set(matches.map((m) => m.id));
    if (!matches.length) { alert("No se encontraron amenazas con ese texto."); render(); return; }
    matches.forEach((m) => ancestorsOf(m.id).forEach((a) => state.collapsed.delete(a)));
    focusNode(matches[0].id);
  } catch { showError(); }
}

function clearVisuals() {
  state.visited.clear();
  state.matches.clear();
  const log = document.getElementById("traversal-log");
  log.hidden = true;
}

document.getElementById("btn-expand").addEventListener("click", () => { state.collapsed.clear(); render(); });
document.getElementById("btn-collapse").addEventListener("click", () => {
  allNodes().filter((n) => n.children.length && n.depth > 0).forEach((n) => state.collapsed.add(n.id));
  render();
});
document.getElementById("btn-center").addEventListener("click", centerView);
document.getElementById("btn-dfs").addEventListener("click", () => runTraversal("dfs"));
document.getElementById("btn-bfs").addEventListener("click", () => runTraversal("bfs"));
document.getElementById("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const query = document.getElementById("search-input").value.trim();
  if (query) { clearVisuals(); search(query); }
});
document.getElementById("btn-reset").addEventListener("click", async () => {
  try {
    await api("/api/reset", { method: "POST" });
    clearVisuals();
    state.selectedId = null;
    const stats = await loadAll();
    collapseDefault();
    render();
    showOverview(stats);
    centerView();
  } catch { showError(); }
});

(async function init() {
  try {
    const stats = await loadAll();
    collapseDefault();
    render();
    showOverview(stats);
    centerView();
  } catch { showError(); }
})();
