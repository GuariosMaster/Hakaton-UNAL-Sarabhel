import { useEffect, useState } from "react";
import { Empty } from "../../components/ui";
import type { ServerAlert } from "../../lib/server";
import { ago, notifyAlert } from "../../lib/util";
import { useAuth } from "../../store/auth";

const REFRESH_MS = 15000;

/** Socorrista: alertas que el puesto de mando asignó a su equipo. */
export function AssignedScreen({ onLocate }: { onLocate?: (lat: number, lon: number) => void }) {
  const session = useAuth((s) => s.session);
  const client = useAuth((s) => s.client)();
  const [alerts, setAlerts] = useState<ServerAlert[]>([]);
  const [error, setError] = useState<string>();
  const [loaded, setLoaded] = useState(false);
  const equipo = session?.equipo?.trim().toLowerCase();

  useEffect(() => {
    if (!client || !equipo) return;
    let known = new Set<number>();
    let first = true;
    const load = async () => {
      try {
        const mine = (await client.alerts(200)).filter((a) => (a.equipo ?? "").trim().toLowerCase() === equipo);
        // Avisar si el puesto de mando asignó algo nuevo.
        if (!first && mine.some((a) => !known.has(a.id) && a.estado !== "atendida")) notifyAlert();
        known = new Set(mine.map((a) => a.id));
        first = false;
        setAlerts(mine);
        setError(undefined);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoaded(true);
      }
    };
    void load();
    const t = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.token, equipo]);

  async function update(a: ServerAlert, changes: { estado?: ServerAlert["estado"]; nota?: string }) {
    if (!client) return;
    try {
      const row = await client.updateAlert(a.id, changes);
      setAlerts((list) => list.map((x) => (x.id === row.id ? row : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!equipo) {
    return <div className="screen"><Empty>No tienes un equipo asignado. Pídele al administrador que te asigne uno.</Empty></div>;
  }
  if (!client) {
    return (
      <div className="screen">
        <Empty>Para ver las alertas asignadas a <b>{session?.equipo}</b> necesitas conexión con el puesto de mando
          (sal y vuelve a entrar conectado a su Wi‑Fi).</Empty>
      </div>
    );
  }

  const pending = alerts.filter((a) => a.estado !== "atendida");
  const done = alerts.filter((a) => a.estado === "atendida");

  return (
    <div className="screen">
      <p className="muted">Equipo <b>{session?.equipo}</b> · se actualiza cada 15 s</p>
      {error && <p className="error">{error}</p>}
      {loaded && alerts.length === 0 && <Empty>No hay alertas asignadas a tu equipo.</Empty>}
      <ul className="list">
        {[...pending, ...done].map((a) => (
          <li key={a.id} className={`alerta ${a.estado}`}>
            <div className="meta">
              <b>{a.type === "zona_riesgo" ? "⚠ Zona de riesgo" : a.type === "bateria_baja" ? "🪫 Batería baja" : "🆘 Emergencia"}</b>
              <span>{ago(a.ts)}</span>
            </div>
            <div className="text">{a.text ?? a.zone ?? `Batería al ${a.battery}%`}</div>
            <div className="meta"><span>{a.long_name ?? a.node_id}</span>
              {a.lat != null && a.lon != null && (
                <a className="link" href={`geo:${a.lat},${a.lon}?q=${a.lat},${a.lon}`}
                   onClick={(e) => { if (onLocate) { e.preventDefault(); onLocate(a.lat!, a.lon!); } }}>📍 Ubicación</a>
              )}
            </div>
            {a.nota && <div className="meta">📝 {a.nota}</div>}
            {a.estado !== "atendida" && (
              <div className="row">
                {a.estado === "nueva" && <button type="button" onClick={() => void update(a, { estado: "en_atencion" })}>🚑 En camino</button>}
                <button type="button" className="primary" onClick={() => {
                  const nota = prompt("Nota para el puesto de mando (opcional):", a.nota ?? "");
                  void update(a, { estado: "atendida", ...(nota ? { nota } : {}) });
                }}>✓ Atendida</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
