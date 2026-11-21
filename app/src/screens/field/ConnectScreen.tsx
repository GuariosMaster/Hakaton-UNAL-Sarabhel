import { useState } from "react";
import type { MeshNode } from "../../lib/mesh";
import { ago } from "../../lib/util";
import { useAuth } from "../../store/auth";
import { useField } from "../../store/field";
import { AccountCard } from "../AccountScreen";

const STATUS_LABEL = {
  desconectado: "Desconectado",
  conectando: "Conectando…",
  configurando: "Sincronizando…",
  conectado: "Conectado",
} as const;

const KIND_LABEL = {
  albergue: "Wi‑Fi del albergue",
  "red-local": "Wi‑Fi del puesto de mando",
  simulador: "Modo demostración",
} as const;

type Form = "albergue" | "red-local" | null;

/** Conexión del modo Campo: nodo de albergue (Wi-Fi del ESP32), puesto de mando o demo. */
export function ConnectCard({ compact = false }: { compact?: boolean }) {
  const {
    status, detail, kind, connect, disconnect, setNodeUrl, serverUrl, deviceName, setLanSettings,
  } = useField();
  const busy = status === "conectando" || status === "configurando";
  const loggedIn = useAuth((s) => !!s.session?.token);
  const [form, setForm] = useState<Form>(null);
  const url = useAuth((st) => st.session?.serverUrl) ?? serverUrl;
  const name = useAuth((st) => st.session?.nombre) ?? deviceName;

  if (status === "conectado") {
    return (
      <div className="card">
        <p><b>{STATUS_LABEL[status]}</b> · {KIND_LABEL[kind]}</p>
        {kind === "red-local" && <p className="muted">Como “{deviceName}” en {serverUrl}</p>}
        {kind === "albergue" && <p className="muted">Nodo ESP32 (192.168.4.1)</p>}
        <button type="button" onClick={() => void disconnect()}>Desconectar</button>
      </div>
    );
  }

  return (
    <div className={`card ${compact ? "warn" : ""}`}>
      <p><b>{busy ? (detail ?? STATUS_LABEL[status]) : "Conexión con el nodo ESP32"}</b></p>
      {!compact && (
        <p className="muted">
          Conéctate al Wi‑Fi <b>“Emergencia …”</b> del nodo ESP32 (192.168.4.1). No requiere internet ni datos móviles.
        </p>
      )}
      {detail && status === "desconectado" && detail !== "usuario" && <p className="error">{detail}</p>}
      <button type="button" className="primary" disabled={busy}
              onClick={() => {
                setNodeUrl("http://192.168.4.1");
                void connect("albergue");
              }}>
        📡 Conectar al nodo ESP32 (Wi‑Fi)
      </button>
      <div className="row">
        {loggedIn && (
          <button type="button" disabled={busy} onClick={() => setForm(form === "red-local" ? null : "red-local")}>
            🖥️ Puesto de mando
          </button>
        )}
        <button type="button" disabled={busy} onClick={() => void connect("simulador")}>🧪 Demo</button>
      </div>

      {form === "red-local" && (
        <form className="lan-form" onSubmit={(e) => {
          e.preventDefault();
          setLanSettings(url.trim(), name.trim() || deviceName);
          void connect("red-local");
        }}>
          <p className="muted">
            Si estás en el puesto de mando, conéctate a su Wi‑Fi.
          </p>
          <button type="submit" className="primary" disabled={busy}>Conectar al puesto de mando</button>
        </form>
      )}
    </div>
  );
}

function energyLine(n: MeshNode) {
  const parts: string[] = [];
  if (n.battery != null) parts.push(`🔋 ${n.battery}%${n.voltage != null ? ` (${n.voltage.toFixed(1)} V)` : ""}`);
  if (n.panelV != null) parts.push(n.panelV > 1 ? `☀️ ${n.panelV.toFixed(1)} V` : "🌙 sin sol");
  return parts.join(" · ") || "🔋 —";
}

export function ConnectScreen({ onChangeMode }: { onChangeMode?: () => void }) {
  const { nodes, myNum, kind } = useField();
  const { session, logout } = useAuth();
  const list = Object.values(nodes).sort((a, b) => (b.lastHeard ?? 0) - (a.lastHeard ?? 0));
  const me = myNum != null ? nodes[myNum] : undefined;

  return (
    <div className="screen">
      <ConnectCard />
      {session ? <AccountCard /> : (
        <div className="card">
          <p><b>Estás sin cuenta</b> (modo emergencia)</p>
          <p className="muted">Puedes pedir ayuda y enviar mensajes. Los socorristas y el puesto de mando entran con su usuario.</p>
          <button type="button" onClick={() => void logout()}>👤 Entrar con usuario</button>
        </div>
      )}
      {me && (
        <div className="card">
          <p><b>{kind === "red-local" ? "Este teléfono" : "Nodo del albergue"}:</b> {me.longName ?? me.id}</p>
          {kind !== "red-local" && <p className="muted">{energyLine(me)}</p>}
        </div>
      )}

      <h2>Nodos en la red ({list.length})</h2>
      <ul className="list">
        {list.map((n) => (
          <li key={n.num}>
            <div className="meta">
              <b>{n.longName ?? n.id}{n.num === myNum ? " (este)" : ""}</b>
              <span>{ago(n.lastHeard)}</span>
            </div>
            <div className="meta">
              <span>{energyLine(n)}</span>
              <span>{n.lat != null ? `📍 ${ago(n.posTime)}` : "📍 —"}</span>
            </div>
          </li>
        ))}
      </ul>

      {onChangeMode && (
        <button type="button" className="link block" onClick={onChangeMode}>Cambiar a modo Puesto de mando</button>
      )}
    </div>
  );
}
