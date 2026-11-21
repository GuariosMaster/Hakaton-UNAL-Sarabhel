import { useRef, useState } from "react";
import { QUICK_MESSAGES } from "../../lib/priority";
import { ago } from "../../lib/util";
import { useField } from "../../store/field";
import { ConnectCard } from "./ConnectScreen";

const HOLD_MS = 1500;
const STATUS_TEXT = {
  "en-cola": "🕓 Sin conexión: se enviará al reconectar",
  enviando: "Enviando por radio…",
  "en-red": "✓ Enviado por radio al puesto de mando",
  entregado: "✓ Entregado",
  fallo: "✗ No se pudo enviar",
} as const;

export function SosScreen() {
  const { status, fix, gpsError, messages, sendEmergency, locate } = useField();
  const connected = status === "conectado";
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string>();
  const [confirm, setConfirm] = useState<{ label: string; text: string }>();
  const timer = useRef<number | undefined>(undefined);
  const lastMine = [...messages].reverse().find((m) => m.mine);

  async function fire(text: string) {
    setError(undefined);
    try {
      await sendEmergency(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  // Mantener presionado para evitar SOS accidentales.
  function startHold() {
    const t0 = performance.now();
    const step = () => {
      const p = Math.min(1, (performance.now() - t0) / HOLD_MS);
      setProgress(p);
      if (p >= 1) {
        timer.current = undefined;
        setProgress(0);
        navigator.vibrate?.(300);
        void fire("SOS Necesito ayuda");
      } else {
        timer.current = requestAnimationFrame(step);
      }
    };
    timer.current = requestAnimationFrame(step);
  }

  function cancelHold() {
    if (timer.current) cancelAnimationFrame(timer.current);
    timer.current = undefined;
    setProgress(0);
  }

  return (
    <div className="screen sos-screen">
      {!connected && <ConnectCard compact />}

      <div className="sos-wrap">
        <button
          type="button"
          className="sos-button"
          style={{ "--p": progress } as React.CSSProperties}
          onPointerDown={startHold}
          onPointerUp={cancelHold}
          onPointerLeave={cancelHold}
          onPointerCancel={cancelHold}
          onContextMenu={(e) => e.preventDefault()}
        >
          <span className="sos-text">SOS</span>
          <span className="sos-hint">{connected ? "Mantén presionado" : "Mantén presionado · se enviará al conectar"}</span>
        </button>
      </div>

      {lastMine && (
        <p className={`send-status ${lastMine.status}`}>
          {lastMine.text} · {STATUS_TEXT[lastMine.status ?? "enviando"]}
        </p>
      )}
      {error && <p className="error center">{error}</p>}

      <div className="gps-line">
        {fix ? (
          <span>📍 {fix.lat.toFixed(5)}, {fix.lon.toFixed(5)} (±{Math.round(fix.accuracy)} m, {ago(fix.ts)})</span>
        ) : (
          <span>📍 {gpsError ? `GPS: ${gpsError}` : "Ubicación aún no tomada"}</span>
        )}
        <button type="button" className="link" onClick={() => void locate()}>Actualizar</button>
      </div>

      <h2>Mensajes rápidos</h2>
      <div className="quick-grid">
        {QUICK_MESSAGES.map((q) => (
          <button key={q.text} type="button" className="quick"
                  onClick={() => setConfirm({ label: q.label, text: q.text })}>
            <span className="icon">{q.icon}</span>
            {q.label}
          </button>
        ))}
      </div>

      {confirm && (
        <div className="sheet-backdrop" onClick={() => setConfirm(undefined)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <p>¿Enviar <b>“{confirm.label}”</b> con tu ubicación a toda la red?</p>
            <div className="row">
              <button type="button" onClick={() => setConfirm(undefined)}>Cancelar</button>
              <button type="button" className="primary"
                      onClick={() => { const t = confirm.text; setConfirm(undefined); void fire(t); }}>
                Enviar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
