"use strict";

const STALE_MS = 30 * 60 * 1000;   // nodo sin reportar en 30 min = gris
const ALERT_MS = 30 * 60 * 1000;   // nodo con alerta crítica reciente = rojo
const MAX_ITEMS = 200;

const state = { nodes: new Map(), markers: new Map(), trail: null, alerts: 0, maxBytes: 200 };
const $ = (id) => document.getElementById(id);

// ---------- utilidades ----------
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

function ago(ts) {
  if (!ts) return "nunca";
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return new Date(ts * 1000).toLocaleString("es-CO");
}

function nodeName(id) {
  if (!id || id === "^all") return "Todos";
  if (id === "puesto-mando") return "Puesto de mando";
  const n = state.nodes.get(id);
  return (n && (n.long_name || n.short_name)) || id;
}

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join("; ") : body.detail || detail;
    } catch (_) { /* respuesta no JSON */ }
    throw new Error(detail);
  }
  return r.json();
}

// ---------- mapa ----------
let map;

function initMap(cfg) {
  map = L.map("map").setView(cfg.center, 14);
  L.tileLayer(cfg.tile_url, {
    maxZoom: 19,
    attribution: "&copy; colaboradores de OpenStreetMap",
  }).addTo(map);
}

async function loadZones() {
  const data = await api("/api/zones");
  L.geoJSON(data, {
    style: { color: "#d9480f", weight: 2, fillOpacity: 0.12, dashArray: "4 4" },
    onEachFeature: (f, layer) => layer.bindTooltip(f.properties?.name || "Zona de riesgo"),
  }).addTo(map);
}

function nodeColor(n) {
  const now = Date.now();
  if (n.alert_ts && now - n.alert_ts * 1000 < ALERT_MS) return "#c92a2a";
  if (n.risk_zone) return "#d9480f";
  if (!n.last_heard || now - n.last_heard * 1000 > STALE_MS) return "#9aa0a6";
  return "#2f9e44";
}

function popupContent(n) {
  const box = el("div");
  box.append(el("b", null, nodeName(n.node_id)), el("br"));
  box.append(el("small", null, n.node_id), el("br"));
  if (n.battery != null || n.voltage != null) {
    box.append(`🔋 Batería: ${n.battery ?? "—"}%${n.voltage != null ? ` (${n.voltage.toFixed(2)} V)` : ""}`, el("br"));
  }
  if (n.panel_v != null) box.append(`☀️ Panel: ${n.panel_v.toFixed(1)} V`, el("br"));
  if (n.rssi != null) box.append(`📶 Señal: ${Math.round(n.rssi)} dBm`, el("br"));
  box.append(`Escuchado: ${ago(n.last_heard)}`, el("br"));
  if (n.lat != null) box.append(`Posición: ${n.lat.toFixed(5)}, ${n.lon.toFixed(5)} (${ago(n.pos_ts)})`, el("br"));
  if (n.risk_zone) box.append(el("b", null, `⚠ En zona de riesgo: ${n.risk_zone}`), el("br"));
  const btn = el("button", "popup-btn", "Ver recorrido");
  btn.type = "button";
  btn.onclick = () => showTrail(n.node_id);
  box.append(btn);
  return box;
}

function renderMarker(n) {
  if (n.lat == null || n.lon == null) return;
  let m = state.markers.get(n.node_id);
  if (!m) {
    m = L.circleMarker([n.lat, n.lon], { radius: 9, weight: 2, fillOpacity: 0.85 }).addTo(map);
    m.bindTooltip("", { permanent: true, direction: "right", offset: [8, 0], className: "node-label" });
    state.markers.set(n.node_id, m);
  }
  const c = nodeColor(n);
  m.setLatLng([n.lat, n.lon]).setStyle({ color: c, fillColor: c });
  m.setTooltipContent(n.short_name || n.node_id);
  m.bindPopup(() => popupContent(state.nodes.get(n.node_id)));
}

async function showTrail(nodeId) {
  const pts = await api(`/api/positions/${encodeURIComponent(nodeId)}`);
  if (state.trail) state.trail.remove();
  if (!pts.length) return;
  state.trail = L.polyline(pts.map((p) => [p.lat, p.lon]), { color: "#2563eb", weight: 3, opacity: 0.8 }).addTo(map);
  map.fitBounds(state.trail.getBounds(), { padding: [40, 40], maxZoom: 17 });
}

function focus(lat, lon) {
  if (lat != null && lon != null) map.flyTo([lat, lon], 17);
}

// ---------- nodos ----------
function upsertNode(n) {
  const prev = state.nodes.get(n.node_id) || {};
  const merged = { ...prev };
  for (const [k, v] of Object.entries(n)) if (v !== undefined) merged[k] = v;
  state.nodes.set(n.node_id, merged);
  renderMarker(merged);
  scheduleNodeList();
}

let nodeListTimer = null;
function scheduleNodeList() {
  if (!nodeListTimer) nodeListTimer = setTimeout(() => { nodeListTimer = null; renderNodeList(); }, 200);
}

function renderNodeList() {
  const list = $("nodes");
  const select = $("send-to");
  const selected = select.value;
  const nodes = [...state.nodes.values()].sort((a, b) => (b.last_heard || 0) - (a.last_heard || 0));
  list.replaceChildren();
  select.replaceChildren(new Option("Todos los nodos", ""));
  for (const n of nodes) {
    const li = el("li", "clickable");
    const meta = el("div", "meta");
    const name = el("b", null, nodeName(n.node_id));
    name.style.color = nodeColor(n);
    meta.append(name, el("span", null, ago(n.last_heard)));
    li.append(meta);
    const info = [];
    if (n.battery != null) info.push(`🔋 ${n.battery}%`);
    if (n.panel_v != null) info.push(n.panel_v > 1 ? `☀️ ${n.panel_v.toFixed(1)} V` : "🌙 sin sol");
    info.push(n.lat != null ? `📍 ${ago(n.pos_ts)}` : "📍 sin GPS");
    if (n.risk_zone) info.push("⚠ zona de riesgo");
    li.append(el("div", "meta", info.join(" · ")));
    li.onclick = () => {
      focus(n.lat, n.lon);
      state.markers.get(n.node_id)?.openPopup();
    };
    list.append(li);
    select.append(new Option(nodeName(n.node_id), n.node_id));
  }
  select.value = selected;
  $("node-count").textContent = nodes.length;
  renderEnergy(nodes);
}

// ---------- energía de los nodos (micro-redes solares) ----------
function renderEnergy(nodes) {
  const list = $("energy");
  const withEnergy = nodes.filter((n) => n.battery != null || n.voltage != null)
    .sort((a, b) => (a.battery ?? 101) - (b.battery ?? 101));  // los más críticos primero
  list.replaceChildren();
  for (const n of withEnergy) {
    const li = el("li");
    const pct = n.battery ?? 0;
    const tone = pct < 20 ? "low" : pct < 50 ? "mid" : "ok";
    const meta = el("div", "meta");
    meta.append(el("b", null, nodeName(n.node_id)), el("span", null, ago(n.energy_ts || n.last_heard)));
    const bar = el("div", `bar ${tone}`);
    const fill = el("span");
    fill.style.width = `${Math.max(2, Math.min(100, pct))}%`;
    bar.append(fill);
    const detail = el("div", "meta");
    detail.append(
      el("span", null, `🔋 ${n.battery ?? "—"}%${n.voltage != null ? ` · ${n.voltage.toFixed(2)} V` : ""}`),
      el("span", null, n.panel_v != null ? (n.panel_v > 1 ? `☀️ ${n.panel_v.toFixed(1)} V` : "🌙 sin sol") : ""),
    );
    li.append(meta, bar, detail);
    list.append(li);
  }
  const low = withEnergy.filter((n) => (n.battery ?? 100) < 20).length;
  $("energy-count").textContent = low ? `${low} baja${low > 1 ? "s" : ""}` : withEnergy.length;
  $("energy-count").className = low ? "count warn" : "count";
  $("energy-empty").hidden = withEnergy.length > 0;
}

// ---------- mensajes y alertas ----------
function messageItem(m) {
  const li = el("li", `${m.priority} ${m.direction === "out" ? "out" : ""}`);
  const meta = el("div", "meta");
  const who = m.direction === "out"
    ? `Puesto de mando → ${nodeName(m.to_node)}`
    : (m.long_name || nodeName(m.from_node));
  const left = el("span");
  left.append(el("b", null, who), " ", el("span", `badge ${m.priority}`, m.priority));
  meta.append(left, el("span", null, ago(m.ts)));
  li.append(meta, el("div", "text", m.text));
  if (m.lat != null) {
    li.classList.add("clickable");
    li.title = "Ver en el mapa";
    li.onclick = () => focus(m.lat, m.lon);
  }
  return li;
}

function addMessage(m, prepend = true) {
  const list = $("messages");
  const li = messageItem(m);
  prepend ? list.prepend(li) : list.append(li);
  while (list.children.length > MAX_ITEMS) list.lastChild.remove();
}

function addAlert(a, prepend = true) {
  const li = el("li", "critico clickable");
  const meta = el("div", "meta");
  const titles = { zona_riesgo: "Entró en zona de riesgo", bateria_baja: "Batería baja", mensaje_critico: "Mensaje crítico" };
  const title = titles[a.type] || "Alerta";
  const body = a.type === "zona_riesgo" ? a.zone
    : a.type === "bateria_baja" ? `Batería al ${a.battery}%${a.voltage != null ? ` (${a.voltage.toFixed(2)} V)` : ""}: revisar el kit de energía`
    : a.text;
  meta.append(el("b", null, `${title} · ${a.long_name || nodeName(a.from_node)}`), el("span", null, ago(a.ts)));
  li.append(meta, el("div", "text", body));
  li.append(el("div", "meta", a.lat != null ? `📍 ${a.lat.toFixed(5)}, ${a.lon.toFixed(5)}` : "📍 posición desconocida"));
  li.onclick = () => focus(a.lat, a.lon);
  const list = $("alerts");
  prepend ? list.prepend(li) : list.append(li);
  while (list.children.length > 50) list.lastChild.remove();
  state.alerts = list.children.length;
  $("alert-count").textContent = state.alerts;
  $("alerts-empty").hidden = state.alerts > 0;
}

// ---------- envío ----------
function initSendForm(maxBytes) {
  const input = $("send-text");
  const counter = $("send-bytes");
  const err = $("send-error");
  const enc = new TextEncoder();
  const update = () => {
    const n = enc.encode(input.value.trim()).length;
    counter.textContent = `${n} / ${maxBytes}`;
    counter.style.color = n > maxBytes ? "var(--crit)" : "";
  };
  input.addEventListener("input", update);
  update();

  $("send-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    const btn = e.submitter;
    btn.disabled = true;
    err.hidden = true;
    try {
      await api("/api/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, to: $("send-to").value || null }),
      });
      input.value = "";
      update();
    } catch (ex) {
      err.textContent = `No se pudo enviar: ${ex.message}`;
      err.hidden = false;
    } finally {
      btn.disabled = false;
    }
  });
}

// ---------- eventos en vivo ----------
function connectStream() {
  const es = new EventSource("/api/stream");
  const dot = $("conn-dot");
  const txt = $("conn-text");
  es.onopen = () => { dot.className = "dot on"; txt.textContent = "En vivo"; };
  es.onerror = () => { dot.className = "dot off"; txt.textContent = "Sin conexión con el servidor"; };
  const on = (name, fn) => es.addEventListener(name, (e) => fn(JSON.parse(e.data)));
  on("msg", (m) => addMessage(m));
  on("node", (n) => upsertNode(n));
  on("position", (p) => upsertNode({ node_id: p.node_id, lat: p.lat, lon: p.lon, alt: p.alt,
                                     pos_ts: p.ts, risk_zone: p.risk_zone, last_heard: p.ts }));
  on("alert", (a) => {
    addAlert(a);
    if (a.type === "mensaje_critico") upsertNode({ node_id: a.from_node, alert_ts: a.ts });
  });
}

// ---------- arranque ----------
async function main() {
  const cfg = await api("/api/config");
  state.maxBytes = cfg.max_text_bytes;
  initMap(cfg);
  initSendForm(cfg.max_text_bytes);
  connectStream();  // antes de cargar historial para no perder eventos

  const [nodes, messages] = await Promise.all([api("/api/nodes"), api("/api/messages?limit=100"), loadZones()]);
  nodes.forEach(upsertNode);
  messages.forEach((m) => addMessage(m, false));
  messages.filter((m) => m.priority === "critico" && m.direction === "in")
          .slice(0, 20)
          .forEach((m) => addAlert({ type: "mensaje_critico", ...m }, false));

  // Refresca colores y "hace X min" aunque no lleguen eventos.
  setInterval(() => {
    state.nodes.forEach(renderMarker);
    renderNodeList();
  }, 30000);
}

main().catch((e) => {
  $("conn-text").textContent = `Error al iniciar: ${e.message}`;
  $("conn-dot").className = "dot off";
});
