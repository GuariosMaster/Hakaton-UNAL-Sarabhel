import { useState, type FormEvent, type ReactNode } from "react";
import type { Priority } from "../lib/priority";
import { MAX_TEXT_BYTES, utf8Bytes } from "../lib/util";

export interface Tab<T extends string> {
  id: T;
  label: string;
  icon: string;
  badge?: number;
}

export function BottomNav<T extends string>({ tabs, active, onChange }: {
  tabs: Tab<T>[];
  active: T;
  onChange: (t: T) => void;
}) {
  return (
    <nav className="bottom-nav">
      {tabs.map((t) => (
        <button key={t.id} type="button" className={t.id === active ? "active" : ""} onClick={() => onChange(t.id)}>
          <span className="icon">{t.icon}</span>
          <span>{t.label}</span>
          {t.badge ? <span className="nav-badge">{t.badge}</span> : null}
        </button>
      ))}
    </nav>
  );
}

export function Header({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <header className="top">
      <h1>{title}</h1>
      {right}
    </header>
  );
}

export function Pill({ tone, children, onClick }: { tone: "ok" | "warn" | "off"; children: ReactNode; onClick?: () => void }) {
  return (
    <button type="button" className={`pill ${tone}`} onClick={onClick} disabled={!onClick}>
      <span className="dot" />
      {children}
    </button>
  );
}

export function PriorityBadge({ p }: { p: Priority }) {
  return <span className={`badge ${p}`}>{p}</span>;
}

export const EDAN_MAP: Record<string, { name: string; icon: string }> = {
  SAL: { name: "Salud", icon: "🏥" },
  RES: { name: "Búsqueda y Rescate", icon: "⛑️" },
  AGU: { name: "Agua y Saneamiento", icon: "💧" },
  ALI: { name: "Alimentación", icon: "🍲" },
  ALB: { name: "Albergue Temporal", icon: "⛺" },
  INF: { name: "Infraestructura", icon: "🏗️" },
  SEG: { name: "Seguridad y Orden", icon: "🛡️" },
  COM: { name: "Comunicaciones", icon: "📡" },
  PRO: { name: "Protección Vulnerables", icon: "🤝" },
  AMB: { name: "Medio Ambiente", icon: "🌳" },
  LOG: { name: "Logística y Transporte", icon: "🚚" },
  GEN: { name: "General / Otro", icon: "ℹ️" },
};

export function EdanBadge({ code, sub }: { code: string; sub?: string | null }) {
  const up = (code || "").toUpperCase();
  const info = EDAN_MAP[up] || { name: code, icon: "🏷️" };
  const cls = `badge edan edan-${up.toLowerCase()}`;
  const title = sub ? `${info.name} → ${sub}` : info.name;
  return (
    <span className={cls} title={title}>
      {info.icon} {up}{sub ? ` · ${sub}` : ""}
    </span>
  );
}

export function NeedsChips({ needs }: { needs?: string[] | string | null }) {
  let list: string[] = [];
  if (Array.isArray(needs)) {
    list = needs;
  } else if (typeof needs === "string" && needs.trim()) {
    try {
      const p = JSON.parse(needs);
      if (Array.isArray(p)) list = p;
      else list = [needs];
    } catch {
      list = needs.split(",").map((s) => s.trim()).filter(Boolean);
    }
  }
  if (list.length === 0) return null;
  return (
    <div className="needs-row">
      <span className="needs-title">Necesidades:</span>
      {list.map((n, i) => (
        <span key={i} className="chip">{n}</span>
      ))}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}

/** Caja para escribir mensajes con contador de bytes (límite de un paquete de radio FSK). */
export function Composer({ onSend, disabled, destinations }: {
  onSend: (text: string, to: string) => Promise<void>;
  disabled?: boolean;
  destinations: { id: string; label: string }[];
}) {
  const [text, setText] = useState("");
  const [to, setTo] = useState(destinations[0]?.id ?? "^all");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const bytes = utf8Bytes(text.trim());
  const tooLong = bytes > MAX_TEXT_BYTES;

  async function submit(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t || tooLong) return;
    setBusy(true);
    setError(undefined);
    try {
      await onSend(t, to);
      setText("");
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <div className="row">
        <select value={to} onChange={(e) => setTo(e.target.value)} aria-label="Destinatario">
          {destinations.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
        </select>
        <span className={`bytes ${tooLong ? "over" : ""}`}>{bytes}/{MAX_TEXT_BYTES}</span>
      </div>
      <div className="row">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Escribe un mensaje…"
               disabled={disabled || busy} aria-label="Mensaje" />
        <button type="submit" className="primary" disabled={disabled || busy || !text.trim() || tooLong}>Enviar</button>
      </div>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
