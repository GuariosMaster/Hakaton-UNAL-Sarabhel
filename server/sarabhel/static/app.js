"use strict";

const STALE_MS = 30 * 60 * 1000;   // nodo sin reportar en 30 min = gris
const ALERT_MS = 30 * 60 * 1000;   // nodo con alerta crítica reciente = rojo
const MAX_ITEMS = 200;

const state = { nodes: new Map(), markers: new Map(), trail: null, alerts: 0, maxBytes: 200, energy: null };

// Autonomía estimada sin sol (horas) con el kit de energía configurado en el servidor.
function autonomyHours(n) {
  const e = state.energy;
  if (!e || n.battery == null || !e.consumption_w) return null;
  return (n.battery / 100) * e.battery_wh * e.dod / e.consumption_w;
}

function fmtHours(h) {
  if (h == null) return "";
  return h >= 48 ? `≈ ${(h / 24).toFixed(1)} días` : `≈ ${Math.round(h)} h`;
}
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

// ---------- sesión ----------
const session = {
  get token() { try { return localStorage.getItem("token"); } catch (_) { return null; } },
  set token(v) { try { v ? localStorage.setItem("token", v) : localStorage.removeItem("token"); } catch (_) { /* sin almacenamiento */ } },
  user: null,
};
const ROL_LABEL = { admin: "Administrador", mando: "Puesto de mando", socorrista: "Socorrista" };

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  const r = await fetch(path, { ...opts, headers });
  if (r.status === 401 && !path.startsWith("/api/auth/login")) {
    session.token = null;
    showLogin("Tu sesión venció. Vuelve a entrar.");
    throw new Error("Sesión vencida");
  }
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
  m.setTooltipContent(n.short_name || (n.long_name ? n.long_name.slice(0, 18) : n.node_id));
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
    const h = autonomyHours(n);
    if (h != null) detail.append(el("span", null, `⏱ ${fmtHours(h)} sin sol`));
    li.append(meta, bar, detail);
    list.append(li);
  }
  const low = withEnergy.filter((n) => (n.battery ?? 100) < 20).length;
  $("energy-count").textContent = low ? `${low} baja${low > 1 ? "s" : ""}` : withEnergy.length;
  $("energy-count").className = low ? "count warn" : "count";
  $("energy-empty").hidden = withEnergy.length > 0;
}

// ---------- mensajes y alertas ----------
const EDAN_INFO = {
  RES: { label: "Rescate", icon: "🆘", cls: "edan-res" },
  SAL: { label: "Salud", icon: "🏥", cls: "edan-sal" },
  ABA: { label: "Abastecimiento", icon: "📦", cls: "edan-aba" },
  INF: { label: "Infraestructura", icon: "🚧", cls: "edan-inf" },
  NAT: { label: "Fenómeno natural", icon: "🌋", cls: "edan-nat" },
  SER: { label: "Servicios", icon: "⚡", cls: "edan-ser" },
  ALB: { label: "Albergue", icon: "⛺", cls: "edan-alb" },
  COM: { label: "Comunicaciones", icon: "📡", cls: "edan-com" },
  PRO: { label: "Protección", icon: "🛡️", cls: "edan-pro" },
  AMB: { label: "Ambiental", icon: "🌱", cls: "edan-amb" },
  LOG: { label: "Logística", icon: "🚚", cls: "edan-log" },
  GEN: { label: "General", icon: "ℹ️", cls: "edan-gen" },
};

function parseNeeds(raw) {
  if (Array.isArray(raw)) return raw;
  if (!raw) return [];
  try {
    const p = JSON.parse(raw);
    return Array.isArray(p) ? p : [];
  } catch {
    return [];
  }
}

function buildTriageElements(categoria, subcategoria, necesidades, resumen, fuente) {
  const container = el("div", "triage-box");
  const cat = EDAN_INFO[categoria] || EDAN_INFO.GEN;
  const badge = el("span", `badge edan ${cat.cls}`);
  badge.textContent = `${cat.icon} ${categoria} · ${subcategoria || cat.label}`;
  badge.title = `Clasificación EDAN (${fuente || "ia"})`;
  container.append(badge);

  const needs = parseNeeds(necesidades);
  if (needs.length > 0) {
    const row = el("div", "needs-row");
    row.append(el("span", "needs-title", "🏷️ Necesidades: "));
    for (const item of needs) {
      row.append(el("span", "chip", item));
    }
    container.append(row);
  }

  if (resumen && resumen.trim()) {
    const resEl = el("div", "ai-resumen");
    resEl.textContent = `🤖 ${resumen.trim()}`;
    container.append(resEl);
  }
  return container;
}

function updateMessageTriage(t) {
  const li = $(`msg-${t.message_id}`);
  if (!li) return;
  if (t.prioridad === "critico") {
    li.className = `critico ${li.classList.contains("out") ? "out" : ""} ${li.classList.contains("clickable") ? "clickable" : ""}`;
    const pBadge = li.querySelector(".meta .badge");
    if (pBadge) {
      pBadge.className = "badge critico";
      pBadge.textContent = "critico";
    }
  }
  const oldBox = li.querySelector(".triage-box");
  if (oldBox) oldBox.remove();
  li.append(buildTriageElements(t.categoria, t.subcategoria, t.necesidades, t.resumen, t.fuente));
}

function messageItem(m) {
  const li = el("li", `${m.priority} ${m.direction === "out" ? "out" : ""}`);
  li.id = `msg-${m.id}`;
  const meta = el("div", "meta");
  const who = m.direction === "out"
    ? `Puesto de mando → ${nodeName(m.to_node)}`
    : (m.long_name || nodeName(m.from_node));
  const left = el("span");
  left.append(el("b", null, who), " ", el("span", `badge ${m.priority}`, m.priority));
  meta.append(left, el("span", null, ago(m.ts)));
  li.append(meta, el("div", "text", m.text));

  if (m.ai_categoria) {
    li.append(buildTriageElements(m.ai_categoria, m.ai_subcategoria, m.ai_necesidades, m.ai_resumen, m.ai_fuente));
  }

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

// ---------- gateways y red ----------
let gwLayer = null;

function rssiColor(r) {
  if (r == null) return "#9aa0a6";
  return r > -80 ? "#2f9e44" : r > -95 ? "#d97706" : "#c92a2a";
}

async function loadGateways() {
  let gws;
  try { gws = await api("/api/gateways"); } catch (_) { return; }
  // Lista
  const list = $("gateways");
  list.replaceChildren();
  const unico = new Map();  // nodo -> cantidad de gateways que lo oyen
  gws.forEach((g) => g.enlaces.forEach((l) => unico.set(l.node_id, (unico.get(l.node_id) || 0) + 1)));
  for (const g of gws) {
    const li = el("li", g.estado === "conectado" ? "" : "critico");
    const meta = el("div", "meta");
    const name = el("b", null, `${g.estado === "conectado" ? "🟢" : "🔴"} ${g.nombre || g.gateway_id}`);
    meta.append(name, el("span", null, g.estado === "conectado" ? ago(g.last_seen) : "desconectado"));
    const detail = el("div", "meta");
    const solos = g.enlaces.filter((l) => unico.get(l.node_id) === 1).length;
    detail.append(
      el("span", null, `📡 ${g.nodos} nodo${g.nodos === 1 ? "" : "s"}${solos ? ` · ${solos} solo por aquí` : ""}`),
      el("span", null, g.battery != null ? `🔋 ${g.battery}%` : (g.conexion || "")),
    );
    li.append(meta, detail);
    if (g.enlaces.length) {
      li.append(el("div", "meta small", g.enlaces.slice(0, 6)
        .map((l) => `${l.long_name || l.node_id} ${Math.round(l.rssi_prom ?? l.rssi ?? 0)} dBm`).join(" · ")));
    }
    if (g.lat != null) { li.classList.add("clickable"); li.onclick = () => focus(g.lat, g.lon); }
    list.append(li);
  }
  const conectados = gws.filter((g) => g.estado === "conectado").length;
  $("gw-count").textContent = gws.length ? `${conectados}/${gws.length}` : "0";
  $("gw-count").className = gws.length && conectados < gws.length ? "count warn" : "count";
  $("gw-empty").hidden = gws.length > 0;

  // Mapa: gateways (cuadrados) y enlaces con cada nodo, color según la señal
  if (!map) return;
  gwLayer?.remove();
  gwLayer = L.layerGroup().addTo(map);
  for (const g of gws) {
    if (g.lat == null || g.lon == null) continue;
    for (const l of g.enlaces) {
      const n = state.nodes.get(l.node_id);
      if (!n || n.lat == null) continue;
      L.polyline([[g.lat, g.lon], [n.lat, n.lon]], {
        color: rssiColor(l.rssi_prom ?? l.rssi), weight: 2, opacity: g.estado === "conectado" ? 0.7 : 0.25,
        dashArray: g.estado === "conectado" ? null : "4 6",
      }).bindTooltip(`${g.nombre || g.gateway_id} ↔ ${l.long_name || l.node_id}: ${Math.round(l.rssi_prom ?? l.rssi ?? 0)} dBm`)
        .addTo(gwLayer);
    }
    const color = g.estado === "conectado" ? "#2563eb" : "#c92a2a";
    L.marker([g.lat, g.lon], {
      icon: L.divIcon({ className: "gw-icon", html: `<span style="background:${color}">📡</span>`, iconSize: [26, 26] }),
    }).bindTooltip(`${g.nombre || g.gateway_id} (${g.estado})`).addTo(gwLayer);
  }
}

// ---------- alertas y su gestión ----------
const alertMap = new Map();  // id -> alerta
const ESTADOS = { nueva: "Nueva", en_atencion: "En atención", atendida: "Atendida" };

function upsertAlert(a) {
  if (a.id == null) return;
  alertMap.set(a.id, { ...(alertMap.get(a.id) || {}), ...a });
  renderAlerts();
}

async function updateAlert(id, changes) {
  try {
    const row = await api(`/api/alerts/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes),
    });
    upsertAlert(row);
  } catch (e) {
    alert(`No se pudo actualizar la alerta: ${e.message}`);
  }
}

function alertBody(a) {
  if (a.type === "zona_riesgo") return a.zone;
  if (a.type === "gateway_desconectado") return `${a.text}. Los albergues que solo llegan por este gateway quedan sin comunicación.`;
  if (a.type === "bateria_baja") return `Batería al ${a.battery}%: revisar el kit de energía`;
  return a.text;
}

function actionButton(label, onClick) {
  const b = el("button", "mini", label);
  b.type = "button";
  b.onclick = (e) => { e.stopPropagation(); onClick(); };
  return b;
}

function renderAlerts() {
  const order = { nueva: 0, en_atencion: 1, atendida: 2 };
  const items = [...alertMap.values()].sort((x, y) => (order[x.estado] - order[y.estado]) || (y.ts - x.ts)).slice(0, 60);
  const list = $("alerts");
  list.replaceChildren();
  const titles = { zona_riesgo: "Zona de riesgo", bateria_baja: "Batería baja", mensaje_critico: "Mensaje crítico",
                   gateway_desconectado: "Gateway desconectado" };
  for (const a of items) {
    const li = el("li", `alerta ${a.estado} clickable`);
    const meta = el("div", "meta");
    const left = el("span");
    left.append(el("b", null, `${titles[a.type] || "Alerta"} · ${a.long_name || nodeName(a.node_id)}`), " ",
                el("span", `estado ${a.estado}`, ESTADOS[a.estado] || a.estado));
    meta.append(left, el("span", null, ago(a.ts)));
    li.append(meta, el("div", "text", alertBody(a)));
    const info = [];
    info.push(a.lat != null ? `📍 ${a.lat.toFixed(5)}, ${a.lon.toFixed(5)}` : "📍 posición desconocida");
    if (a.equipo) info.push(`👥 ${a.equipo}`);
    li.append(el("div", "meta", info.join(" · ")));
    if (a.nota) li.append(el("div", "nota", `📝 ${a.nota}`));
    const actions = el("div", "acciones");
    if (a.estado === "nueva") actions.append(actionButton("Atender", () => updateAlert(a.id, { estado: "en_atencion" })));
    if (a.estado !== "atendida") actions.append(actionButton("✓ Atendida", () => updateAlert(a.id, { estado: "atendida" })));
    else actions.append(actionButton("Reabrir", () => updateAlert(a.id, { estado: "nueva" })));
    actions.append(actionButton("👥 Equipo", () => {
      const v = prompt("Equipo de rescate asignado:", a.equipo || "");
      if (v !== null) updateAlert(a.id, { equipo: v.trim(), ...(a.estado === "nueva" && v.trim() ? { estado: "en_atencion" } : {}) });
    }));
    actions.append(actionButton("📝 Nota", () => {
      const v = prompt("Nota:", a.nota || "");
      if (v !== null) updateAlert(a.id, { nota: v.trim() });
    }));
    li.append(actions);
    li.onclick = () => focus(a.lat, a.lon);
    list.append(li);
  }
  const pending = items.filter((a) => a.estado !== "atendida").length;
  $("alert-count").textContent = pending;
  $("alert-count").className = pending ? "count warn" : "count";
  $("alerts-empty").hidden = items.length > 0;
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
  const es = new EventSource(`/api/stream?token=${encodeURIComponent(session.token)}`);
  const dot = $("conn-dot");
  const txt = $("conn-text");
  es.onopen = () => { dot.className = "dot on"; txt.textContent = "En vivo"; };
  es.onerror = () => { dot.className = "dot off"; txt.textContent = "Sin conexión con el servidor"; };
  const on = (name, fn) => es.addEventListener(name, (e) => fn(JSON.parse(e.data)));
  on("msg", (m) => addMessage(m));
  on("triage", (t) => updateMessageTriage(t));
  on("node", (n) => upsertNode(n));
  on("position", (p) => upsertNode({ node_id: p.node_id, lat: p.lat, lon: p.lon, alt: p.alt,
                                     pos_ts: p.ts, risk_zone: p.risk_zone, last_heard: p.ts }));
  on("alert", (a) => {
    upsertAlert(a);
    if (a.type === "mensaje_critico") upsertNode({ node_id: a.from_node, alert_ts: a.ts });
  });
  on("alert_update", (a) => upsertAlert(a));
  on("gateway", () => loadGateways());
}

// ---------- arranque ----------
async function main() {
  const cfg = await api("/api/config");
  state.maxBytes = cfg.max_text_bytes;
  state.energy = cfg.energy || null;
  initMap(cfg);
  initSendForm(cfg.max_text_bytes);
  connectStream();  // antes de cargar historial para no perder eventos

  const [nodes, messages] = await Promise.all([api("/api/nodes"), api("/api/messages?limit=100"), loadZones()]);
  nodes.forEach(upsertNode);
  messages.forEach((m) => addMessage(m, false));
  (await api("/api/alerts?limit=100")).forEach((a) => alertMap.set(a.id, a));
  renderAlerts();
  await loadGateways();
  setInterval(loadGateways, 15000);  // los enlaces cambian con cada trama

  // Refresca colores y "hace X min" aunque no lleguen eventos.
  setInterval(() => {
    state.nodes.forEach(renderMarker);
    renderNodeList();
    renderAlerts();
  }, 30000);
}

// ---------- inicio de sesión y usuarios ----------
function showLogin(message) {
  $("login").hidden = false;
  fetch("/api/auth/estado").then((r) => r.json())
    .then((e) => { $("login-hint").hidden = !e.admin_inicial; }).catch(() => {});
  $("login-error").textContent = message || "";
  $("login-error").hidden = !message;
  try { $("login-user").value = localStorage.getItem("ultimoUsuario") || ""; } catch (_) { /* nada */ }
  ($("login-user").value ? $("login-pin") : $("login-user")).focus();
}

async function askPinChange(force) {
  const actual = force ? null : prompt("PIN actual:");
  if (!force && actual === null) return;
  const nuevo = prompt(force ? "Debes cambiar el PIN inicial. Nuevo PIN (4 dígitos):" : "Nuevo PIN (4 dígitos):");
  if (nuevo === null) return;
  const actualPin = force ? prompt("Confirma tu PIN actual:") : actual;
  if (actualPin === null) return;
  try {
    await api("/api/auth/pin", { method: "POST", headers: { "Content-Type": "application/json" },
                                 body: JSON.stringify({ actual: actualPin, nuevo }) });
    alert("PIN actualizado");
  } catch (e) {
    alert(`No se pudo cambiar el PIN: ${e.message}`);
    if (force) return askPinChange(true);
  }
}

function applyUser(u) {
  session.user = u;
  $("user-name").textContent = `${u.nombre} · ${ROL_LABEL[u.rol]}`;
  $("btn-usuarios").hidden = u.rol !== "admin";
  const csv = (f) => `/api/export/${f}?token=${encodeURIComponent(session.token)}`;
  $("csv-mensajes").href = csv("mensajes.csv");
  $("csv-alertas").href = csv("alertas.csv");
  const mando = u.rol !== "socorrista";
  $("csv-mensajes").hidden = $("csv-alertas").hidden = !mando;
  $("send-form").hidden = !mando;
}

async function renderUsers() {
  const users = await api("/api/users");
  const body = $("users-body");
  body.replaceChildren();
  for (const u of users) {
    const tr = el("tr", u.activo ? "" : "inactivo");
    tr.append(el("td", null, u.usuario), el("td", null, u.nombre), el("td", null, ROL_LABEL[u.rol]),
              el("td", null, u.equipo || "—"));
    const acts = el("td", "acciones");
    const run = async (fn) => {
      try { await fn(); await renderUsers(); } catch (e) { $("users-error").textContent = e.message; $("users-error").hidden = false; }
    };
    const patch = (data) => api(`/api/users/${encodeURIComponent(u.usuario)}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    acts.append(
      actionButton("PIN", () => { const p = prompt(`Nuevo PIN para ${u.usuario} (4 dígitos):`); if (p) run(() => patch({ pin: p })); }),
      actionButton("Equipo", () => { const v = prompt("Equipo:", u.equipo || ""); if (v !== null) run(() => patch({ equipo: v })); }),
      actionButton("Rol", () => {
        const v = prompt("Rol (admin, mando, socorrista):", u.rol);
        if (v) run(() => patch({ rol: v.trim().toLowerCase() }));
      }),
      actionButton(u.activo ? "Desactivar" : "Activar", () => run(() => patch({ activo: !u.activo }))),
      actionButton("Eliminar", () => {
        if (confirm(`¿Eliminar el usuario ${u.usuario}? No se puede deshacer.`)) {
          run(() => api(`/api/users/${encodeURIComponent(u.usuario)}`, { method: "DELETE" }));
        }
      }),
    );
    tr.append(acts);
    body.append(tr);
  }
}

function initAuthUi() {
  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const usuario = $("login-user").value.trim().toLowerCase();
    try {
      const r = await api("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
                                                body: JSON.stringify({ usuario, pin: $("login-pin").value }) });
      session.token = r.token;
      try { localStorage.setItem("ultimoUsuario", usuario); } catch (_) { /* nada */ }
      $("login-pin").value = "";
      $("login").hidden = true;
      await boot();
      if (r.pin_inicial) await askPinChange(true);
    } catch (ex) {
      $("login-pin").value = "";
      $("login-error").textContent = ex.message;
      $("login-error").hidden = false;
    }
  });
  $("btn-salir").onclick = async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (_) { /* nada */ }
    session.token = null;
    location.reload();
  };
  $("btn-usuario").onclick = () => askPinChange(false);
  $("btn-usuarios").onclick = async () => { $("users").hidden = false; $("users-error").hidden = true; await renderUsers(); };
  $("users-close").onclick = () => { $("users").hidden = true; };
  $("user-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        usuario: $("nu-usuario").value.trim().toLowerCase(), nombre: $("nu-nombre").value.trim(),
        rol: $("nu-rol").value, equipo: $("nu-equipo").value.trim() || null, pin: $("nu-pin").value }) });
      e.target.reset();
      $("users-error").hidden = true;
      await renderUsers();
    } catch (ex) {
      $("users-error").textContent = ex.message;
      $("users-error").hidden = false;
    }
  });
}

let started = false;
async function boot() {
  if (!session.token) return showLogin();
  let user;
  try {
    user = await api("/api/auth/me");
  } catch (_) {
    return;  // api() ya mostró el login
  }
  applyUser(user);
  if (!started) {
    started = true;
    await main();
  }
}

initAuthUi();
boot().catch((e) => {
  $("conn-text").textContent = `Error al iniciar: ${e.message}`;
  $("conn-dot").className = "dot off";
});
