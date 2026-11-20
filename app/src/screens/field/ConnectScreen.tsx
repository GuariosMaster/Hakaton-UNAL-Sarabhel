import { ago } from "../../lib/util";
import { useField } from "../../store/field";

const STATUS_LABEL = {
  desconectado: "Desconectado",
  conectando: "Conectando…",
  configurando: "Sincronizando con el nodo…",
  conectado: "Conectado",
} as const;

/** Tarjeta para conectar el nodo LoRa (Bluetooth) o usar el modo demostración. */
export function ConnectCard({ compact = false }: { compact?: boolean }) {
  const { status, detail, kind, connect, disconnect } = useField();
  const busy = status === "conectando" || status === "configurando";

  if (status === "conectado") {
    return (
      <div className="card">
        <p><b>{STATUS_LABEL[status]}</b> · {kind === "bluetooth" ? "Nodo por Bluetooth" : "Modo demostración"}</p>
        <button type="button" onClick={() => void disconnect()}>Desconectar</button>
      </div>
    );
  }

  return (
    <div className={`card ${compact ? "warn" : ""}`}>
      <p><b>{busy ? STATUS_LABEL[status] : "Conecta tu nodo LoRa"}</b></p>
      {!compact && (
        <p className="muted">
          Enciende tu dispositivo y activa el Bluetooth del teléfono. No se necesita internet ni señal celular.
        </p>
      )}
      {detail && status === "desconectado" && <p className="error">{detail}</p>}
      <div className="row">
        <button type="button" className="primary" disabled={busy} onClick={() => void connect("bluetooth")}>
          🔵 Bluetooth
        </button>
        <button type="button" disabled={busy} onClick={() => void connect("simulador")}>🧪 Modo demo</button>
      </div>
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
