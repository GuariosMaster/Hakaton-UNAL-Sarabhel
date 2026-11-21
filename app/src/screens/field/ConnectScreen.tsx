import { useState } from "react";
import { ago } from "../../lib/util";
import { useField } from "../../store/field";

const STATUS_LABEL = {
  desconectado: "Desconectado",
  conectando: "Conectando…",
  configurando: "Sincronizando con el nodo…",
  conectado: "Conectado",
} as const;

const KIND_LABEL = {
  bluetooth: "Nodo por Bluetooth",
  "red-local": "Red local (Wi‑Fi del puesto de mando)",
  simulador: "Modo demostración",
} as const;

/** Tarjeta para conectar: nodo LoRa por Bluetooth, red local por Wi-Fi o modo demostración. */
export function ConnectCard({ compact = false }: { compact?: boolean }) {
  const { status, detail, kind, connect, disconnect, serverUrl, deviceName, setLanSettings } = useField();
  const busy = status === "conectando" || status === "configurando";
  const [showLan, setShowLan] = useState(false);
  const [url, setUrl] = useState(serverUrl);
  const [name, setName] = useState(deviceName);

  if (status === "conectado") {
    return (
      <div className="card">
        <p><b>{STATUS_LABEL[status]}</b> · {KIND_LABEL[kind]}</p>
        {kind === "red-local" && <p className="muted">Como “{deviceName}” en {serverUrl}</p>}
        <button type="button" onClick={() => void disconnect()}>Desconectar</button>
      </div>
    );
  }

  return (
    <div className={`card ${compact ? "warn" : ""}`}>
      <p><b>{busy ? (detail && kind === "red-local" ? detail : STATUS_LABEL[status]) : "Conecta tu nodo LoRa"}</b></p>
      {!compact && (
        <p className="muted">
          Enciende tu dispositivo y activa el Bluetooth del teléfono. No se necesita internet ni señal celular.
        </p>
      )}
      {detail && status === "desconectado" && detail !== "usuario" && <p className="error">{detail}</p>}
      <div className="row">
        <button type="button" className="primary" disabled={busy} onClick={() => void connect("bluetooth")}>
          🔵 Bluetooth
        </button>
        <button type="button" disabled={busy} onClick={() => setShowLan((v) => !v)}>📶 Red local</button>
      </div>
      <button type="button" disabled={busy} onClick={() => void connect("simulador")}>🧪 Modo demo</button>

      {showLan && (
        <form className="lan-form" onSubmit={(e) => {
          e.preventDefault();
          setLanSettings(url.trim(), name.trim() || deviceName);
          void connect("red-local");
        }}>
          <p className="muted">
            Conéctate al Wi‑Fi del puesto de mando. Tus mensajes llegan a los demás teléfonos y al puesto de mando
            a través del servidor (útil para probar sin nodos LoRa).
          </p>
          <label>Tu nombre en la red
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={40} required />
          </label>
          <label>Servidor
            <input value={url} onChange={(e) => setUrl(e.target.value)} inputMode="url" autoCapitalize="off" required />
          </label>
          <button type="submit" className="primary" disabled={busy}>Conectar por Wi‑Fi</button>
        </form>
      )}
    </div>
  );
}

export function ConnectScreen({ onChangeMode }: { onChangeMode: () => void }) {
  const { nodes, myNum } = useField();
  const list = Object.values(nodes).sort((a, b) => (b.lastHeard ?? 0) - (a.lastHeard ?? 0));
  const me = myNum != null ? nodes[myNum] : undefined;

  return (
    <div className="screen">
      <ConnectCard />
      {me && (
        <div className="card">
          <p><b>Mi nodo:</b> {me.longName ?? me.id}</p>
          <p className="muted">{me.id}{me.battery != null ? ` · Batería ${me.battery}%` : ""}</p>
        </div>
      )}

      <h2>Nodos en la red ({list.length})</h2>
      <ul className="list">
        {list.map((n) => (
          <li key={n.num}>
            <div className="meta">
              <b>{n.longName ?? n.id}{n.num === myNum ? " (yo)" : ""}</b>
              <span>{ago(n.lastHeard)}</span>
            </div>
            <div className="meta">
              <span>{n.battery != null ? `🔋 ${n.battery}%` : "🔋 —"}</span>
              <span>{n.lat != null ? `📍 ${ago(n.posTime)}` : "📍 sin GPS"}</span>
            </div>
          </li>
        ))}
      </ul>

      <button type="button" className="link block" onClick={onChangeMode}>Cambiar a modo Puesto de mando</button>
    </div>
  );
}
