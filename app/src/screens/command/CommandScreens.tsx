import { useState } from "react";
import { MapView, type MapMarker } from "../../components/MapView";
import { Composer, Empty, PriorityBadge } from "../../components/ui";
import type { ServerNode } from "../../lib/server";
import { ago, now } from "../../lib/util";
import { serverNodeName, useCommand } from "../../store/command";

const ALERT_S = 30 * 60;
const STALE_S = 30 * 60;

function nodeColor(n: ServerNode) {
  if (n.alert_ts && now() - n.alert_ts < ALERT_S) return "#c92a2a";
  if (n.risk_zone) return "#d9480f";
  if (!n.last_heard || now() - n.last_heard > STALE_S) return "#9aa0a6";
  return "#2f9e44";
}

export type Focus = { lat: number; lon: number; seq: number };

export function CommandAlertsScreen({ onLocate }: { onLocate: (lat: number, lon: number) => void }) {
  const { alerts, nodes } = useCommand();
  return (
    <div className="screen">
      {alerts.length === 0 && <Empty>Sin alertas críticas por ahora.</Empty>}
      <ul className="list">
        {alerts.map((a, i) => (
          <li key={`${a.ts}-${a.from_node}-${i}`} className="critico clickable"
              onClick={() => a.lat != null && a.lon != null && onLocate(a.lat, a.lon)}>
            <div className="meta">
              <b>{a.type === "zona_riesgo" ? "⚠ Zona de riesgo" : "🆘 Mensaje crítico"}</b>
              <span>{ago(a.ts)}</span>
            </div>
            <div className="text">{a.type === "zona_riesgo" ? a.zone : a.text}</div>
            <div className="meta">
              <span>{a.long_name || serverNodeName(nodes, a.from_node)}</span>
              <span>{a.lat != null ? "📍 Ver en mapa" : "📍 sin ubicación"}</span>
            </div>
          </li>
        ))}
      </ul>
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
      label: n.short_name || n.node_id,
      popup: [
        n.long_name || n.node_id,
        `Escuchado ${ago(n.last_heard)}`,
        n.battery != null ? `Batería ${n.battery}%` : "",
        n.risk_zone ? `⚠ ${n.risk_zone}` : "",
      ].filter(Boolean),
    }));
  return (
    <div className="screen map-screen">
      <MapView markers={markers} zones={zones} tileUrl={tileUrl} focus={focus} />
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

export function CommandSettingsScreen({ onChangeMode }: { onChangeMode: () => void }) {
  const { url, status, error, connect, disconnect, nodes } = useCommand();
  const [value, setValue] = useState(url);
  const busy = status === "conectando";
  return (
    <div className="screen">
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
