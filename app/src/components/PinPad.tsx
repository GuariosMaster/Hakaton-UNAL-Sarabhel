import { useEffect, useState } from "react";

/** Teclado numérico grande para el PIN de 4 dígitos: se envía solo al completar el cuarto. */
export function PinPad({ onComplete, error, busy }: {
  onComplete: (pin: string) => void;
  error?: string;
  busy?: boolean;
}) {
  const [pin, setPin] = useState("");
  const [shake, setShake] = useState(false);

  // Al llegar un error: vibrar, sacudir los puntos y borrar.
  useEffect(() => {
    if (!error) return;
    setPin("");
    setShake(true);
    navigator.vibrate?.([60, 40, 60]);
    const t = setTimeout(() => setShake(false), 450);
    return () => clearTimeout(t);
  }, [error]);

  function press(d: string) {
    if (busy || pin.length >= 4) return;
    navigator.vibrate?.(8);
    const next = pin + d;
    setPin(next);
    if (next.length === 4) onComplete(next);
  }

  // También con el teclado físico (PC o tablet).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT") return;
      if (/^\d$/.test(e.key)) press(e.key);
      else if (e.key === "Backspace") setPin((p) => p.slice(0, -1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="pinpad">
      <div className={`pin-dots ${shake ? "shake" : ""}`} aria-label={`${pin.length} de 4 dígitos`}>
        {[0, 1, 2, 3].map((i) => <span key={i} className={i < pin.length ? "on" : ""} />)}
      </div>
      <div className="keys">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button key={d} type="button" onClick={() => press(d)} disabled={busy}>{d}</button>
        ))}
        <span />
        <button type="button" onClick={() => press("0")} disabled={busy}>0</button>
        <button type="button" className="del" aria-label="Borrar" disabled={busy || !pin}
                onClick={() => setPin((p) => p.slice(0, -1))}>⌫</button>
      </div>
    </div>
  );
}
