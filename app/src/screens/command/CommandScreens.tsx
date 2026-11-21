import { useState } from "react";
import { MapView, type MapMarker } from "../../components/MapView";
import { Composer, Empty, PriorityBadge } from "../../components/ui";
import type { AlertState, ServerAlert, ServerNode } from "../../lib/server";
import { ago, now } from "../../lib/util";
import { serverNodeName, useCommand } from "../../store/command";
import { AccountCard } from "../AccountScreen";

const ALERT_S = 30 * 60;
const STALE_S = 30 * 60;

function nodeColor(n: ServerNode) {
  if (n.alert_ts && now() - n.alert_ts < ALERT_S) return "#c92a2a";
  if (n.risk_zone) return "#d9480f";
  if (!n.last_heard || now() - n.last_heard > STALE_S) return "#9aa0a6";
  return "#2f9e44";
}

export type Focus = { lat: number; lon: number; seq: number };

const ESTADO_LABEL = { nueva: "Nueva", en_atencion: "En atención", atendida: "Atendida" } as const;
const ESTADO_ORDEN = { nueva: 0, en_atencion: 1, atendida: 2 } as const;

function alertTitle(a: ServerAlert) {
  return a.type === "zona_riesgo" ? "⚠ Zona de riesgo" : a.type === "bateria_baja" ? "🪫 Batería baja" : "🆘 Mensaje crítico";
}

function alertBody(a: ServerAlert) {
  return a.type === "zona_riesgo" ? a.zone : a.type === "bateria_baja" ? `Batería al ${a.battery}%: revisar el kit de energía` : a.text;
}

export function CommandAlertsScreen({ onLocate }: { onLocate: (lat: number, lon: number) => void }) {
  const { alerts, nodes, updateAlert } = useCommand();
  const [open, setOpen] = useState<ServerAlert>();
  const [equipo, setEquipo] = useState("");
  const [nota, setNota] = useState("");
  const [error, setError] = useState<string>();
  const sorted = [...alerts].sort((x, y) => (ESTADO_ORDEN[x.estado] - ESTADO_ORDEN[y.estado]) || y.ts - x.ts);

  function edit(a: ServerAlert) {
    setOpen(a);
    setEquipo(a.equipo ?? "");
    setNota(a.nota ?? "");
    setError(undefined);
  }

  async function save(estado?: AlertState) {
    if (!open) return;
    try {
      await updateAlert(open.id, {
        equipo: equipo.trim(), nota: nota.trim(),
        estado: estado ?? (open.estado === "nueva" && equipo.trim() ? "en_atencion" : undefined),
      });
      setOpen(undefined);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="screen">
      {sorted.length === 0 && <Empty>Sin alertas por ahora.</Empty>}
      <ul className="list">
        {sorted.map((a) => (
          <li key={a.id} className={`alerta ${a.estado} clickable`} onClick={() => edit(a)}>
            <div className="meta">
              <b>{alertTitle(a)} <span className={`estado ${a.estado}`}>{ESTADO_LABEL[a.estado]}</span></b>
              <span>{ago(a.ts)}</span>
            </div>
            <div className="text">{alertBody(a)}</div>
            <div className="meta">
              <span>{a.long_name || serverNodeName(nodes, a.from_node ?? a.node_id)}</span>
              {a.lat != null && a.lon != null && (
                <button type="button" className="link" onClick={(e) => { e.stopPropagation(); onLocate(a.lat!, a.lon!); }}>
                  📍 Ver en mapa
                </button>
              )}
            </div>
            {(a.equipo || a.nota) && (
              <div className="meta">{[a.equipo && `👥 ${a.equipo}`, a.nota && `📝 ${a.nota}`].filter(Boolean).join(" · ")}</div>
            )}
          </li>
        ))}
      </ul>

      {open && (
        <div className="sheet-backdrop" onClick={() => setOpen(undefined)}>
          <form className="sheet" onClick={(e) => e.stopPropagation()} onSubmit={(e) => { e.preventDefault(); void save(); }}>
            <p><b>{alertTitle(open)}</b> · {open.long_name || serverNodeName(nodes, open.node_id)}</p>
            <p className="muted">{alertBody(open)}</p>
            <label className="field">Equipo de rescate asignado
              <input value={equipo} onChange={(e) => setEquipo(e.target.value)} maxLength={60} placeholder="Ej: Bomberos 2" />
            </label>
            <label className="field">Nota
              <input value={nota} onChange={(e) => setNota(e.target.value)} maxLength={300} placeholder="Ej: 3 heridos leves" />
            </label>
            {error && <p className="error">{error}</p>}
            <div className="row">
              {open.estado === "nueva" && <button type="button" onClick={() => void save("en_atencion")}>Atender</button>}
              {open.estado !== "atendida"
                ? <button type="button" onClick={() => void save("atendida")}>✓ Atendida</button>
                : <button type="button" onClick={() => void save("nueva")}>Reabrir</button>}
              <button type="submit" className="primary">Guardar</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

export function CommandMapScreen({ focus }: { focus?: Focus }) {
  const { nodes, zones, tileUrl } = useCommand();
  const markers: MapMarker[] = Object.values(nodes)
    .filter((n) => n.lat != null && n.lon != null)
    .map((n) => ({
      id: n.node_id,
      lat: n.lat!,
      lon: n.lon!,
      color: nodeColor(n),
      label: n.short_name || n.long_name?.slice(0, 18) || n.node_id,
      popup: [
        n.long_name || n.node_id,
        `Escuchado ${ago(n.last_heard)}`,
        n.battery != null ? `🔋 Batería ${n.battery}%${n.voltage != null ? ` (${n.voltage.toFixed(1)} V)` : ""}` : "",
        n.panel_v != null ? (n.panel_v > 1 ? `☀️ Panel ${n.panel_v.toFixed(1)} V` : "🌙 Panel sin sol") : "",
        n.risk_zone ? `⚠ ${n.risk_zone}` : "",
      ].filter(Boolean),
    }));
  return (
    <div className="screen map-screen">
      <MapView markers={markers} zones={zones} tileUrl={tileUrl} focus={focus} />
    </div>
  );
}

/** Energía de cada nodo (micro-redes solares): los más críticos primero. */
function autonomy(battery: number | null | undefined, kit?: { battery_wh: number; consumption_w: number; dod: number }) {
  if (battery == null || !kit || !kit.consumption_w) return "";
  const h = (battery / 100) * kit.battery_wh * kit.dod / kit.consumption_w;
  return h >= 48 ? `⏱ ≈ ${(h / 24).toFixed(1)} días sin sol` : `⏱ ≈ ${Math.round(h)} h sin sol`;
}

export function CommandEnergyScreen() {
  const { nodes, energyKit } = useCommand();
  const list = Object.values(nodes)
    .filter((n) => n.battery != null || n.voltage != null)
    .sort((a, b) => (a.battery ?? 101) - (b.battery ?? 101));
  const low = list.filter((n) => (n.battery ?? 100) < 20).length;
  return (
    <div className="screen">
      {list.length === 0 && <Empty>Sin telemetría de energía todavía.</Empty>}
      {list.length > 0 && (
        <div className={`card ${low ? "warn" : ""}`}>
          <p><b>{list.length} nodos reportando</b>{low ? ` · ${low} con batería baja` : " · todos con carga suficiente"}</p>
        </div>
      )}
      <ul className="list">
        {list.map((n) => {
          const pct = n.battery ?? 0;
          return (
            <li key={n.node_id}>
              <div className="meta">
                <b>{n.long_name || n.node_id}</b>
                <span>{ago(n.energy_ts ?? n.last_heard)}</span>
              </div>
              <div className={`bar ${pct < 20 ? "low" : pct < 50 ? "mid" : ""}`}>
                <span style={{ width: `${Math.max(2, Math.min(100, pct))}%` }} />
              </div>
              <div className="meta">
                <span>🔋 {n.battery ?? "—"}%{n.voltage != null ? ` · ${n.voltage.toFixed(2)} V` : ""}</span>
                <span>{n.panel_v != null ? (n.panel_v > 1 ? `☀️ ${n.panel_v.toFixed(1)} V` : "🌙 sin sol") : ""}</span>
              </div>
              {energyKit && n.battery != null && <div className="meta"><span>{autonomy(n.battery, energyKit)}</span></div>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function CommandChatScreen() {
  const { messages, nodes, status, send } = useCommand();
  const destinations = [
    { id: "^all", label: "Todos los nodos" },
    ...Object.values(nodes).map((n) => ({ id: n.node_id, label: n.long_name || n.node_id })),
  ];
  return (
    <div className="screen chat">
      <div className="chat-list reverse">
        {messages.length === 0 && <Empty>Sin mensajes.</Empty>}
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.direction === "out" ? "mine" : ""} ${m.priority}`}>
            <div className="meta">
              <b>{m.direction === "out"
                ? `Puesto de mando → ${serverNodeName(nodes, m.to_node)}`
                : m.long_name || serverNodeName(nodes, m.from_node)}</b>
              {m.priority !== "informativo" && <PriorityBadge p={m.priority} />}
            </div>
            <div className="text">{m.text}</div>
            <div className="meta small"><span>{ago(m.ts)}</span></div>
          </div>
        ))}
      </div>
      <Composer destinations={destinations} disabled={status !== "conectado"}
                onSend={(t, to) => send(t, to === "^all" ? null : to)} />
    </div>
  );
}

export function CommandSettingsScreen({ onChangeMode, onUsers }: { onChangeMode: () => void; onUsers?: () => void }) {
  const { url, status, error, connect, disconnect, nodes } = useCommand();
  const [value, setValue] = useState(url);
  const busy = status === "conectando";
  return (
    <div className="screen">
      <AccountCard />
      {onUsers && (
        <button type="button" className="card-button" onClick={onUsers}>👥 Administrar usuarios <span>›</span></button>
      )}
      <div className="card">
        <p><b>Servidor del puesto de mando</b></p>
        <p className="muted">
          Conecta el teléfono al Wi-Fi del puesto de mando (no necesita internet) y escribe la dirección del servidor.
        </p>
        <input value={value} onChange={(e) => setValue(e.target.value)} inputMode="url" autoCapitalize="off"
               placeholder="http://192.168.137.1:8080" aria-label="Dirección del servidor" />
        <div className="row">
          {status === "conectado"
            ? <button type="button" onClick={disconnect}>Desconectar</button>
            : <button type="button" className="primary" disabled={busy} onClick={() => void connect(value)}>
                {busy ? "Conectando…" : "Conectar"}
              </button>}
        </div>
        {error && <p className="error">{error}</p>}
        {status === "conectado" && <p className="ok">✓ Conectado · {Object.keys(nodes).length} nodos en la red</p>}
      </div>
      <button type="button" className="link block" onClick={onChangeMode}>Cambiar a modo Campo</button>
    </div>
  );
}
