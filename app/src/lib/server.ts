// Cliente del servidor del puesto de mando (server/sarabhel/dashboard.py).
// Se usa en el modo Mando, con el teléfono conectado al Wi-Fi del puesto.
import type { Priority } from "./priority";

export interface ServerNode {
  node_id: string;
  long_name?: string | null;
  short_name?: string | null;
  lat?: number | null;
  lon?: number | null;
  pos_ts?: number | null;
  battery?: number | null;
  last_heard?: number | null;
  risk_zone?: string | null;
  alert_ts?: number | null;
}

export interface ServerMessage {
  id: number;
  direction: "in" | "out";
  from_node: string;
  to_node?: string | null;
  long_name?: string | null;
  text: string;
  priority: Priority;
  lat?: number | null;
  lon?: number | null;
  ts: number;
}

export interface ServerAlert {
  type: "mensaje_critico" | "zona_riesgo";
  from_node: string;
  long_name?: string | null;
  text?: string;
  zone?: string;
  lat?: number | null;
  lon?: number | null;
  ts: number;
}

export interface ServerPosition {
  node_id: string;
  lat: number;
  lon: number;
  ts: number;
  risk_zone?: string | null;
}

export interface StreamHandlers {
  open: () => void;
  error: () => void;
  msg: (m: ServerMessage) => void;
  node: (n: ServerNode) => void;
  position: (p: ServerPosition) => void;
  alert: (a: ServerAlert) => void;
}

export class ServerClient {
  readonly base: string;

  constructor(baseUrl: string) {
    this.base = baseUrl.trim().replace(/\/+$/, "");
    if (!/^https?:\/\//.test(this.base)) this.base = "http://" + this.base;
  }

  private async get<T>(path: string): Promise<T> {
    const r = await fetch(this.base + path, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json() as Promise<T>;
  }

  config() { return this.get<{ tile_url: string; center: [number, number]; max_text_bytes: number }>("/api/config"); }
  nodes() { return this.get<ServerNode[]>("/api/nodes"); }
  messages(limit = 100) { return this.get<ServerMessage[]>(`/api/messages?limit=${limit}`); }
  zones() { return this.get<GeoJSON.FeatureCollection>("/api/zones"); }

  async send(text: string, to?: string | null): Promise<void> {
    const r = await fetch(this.base + "/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, to: to || null }),
      signal: AbortSignal.timeout(8000),
    });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const body = await r.json();
        detail = Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : body.detail;
      } catch { /* sin cuerpo JSON */ }
      throw new Error(detail);
    }
  }

  /** Eventos en vivo (SSE). Devuelve una función para cerrar la conexión. */
  stream(h: StreamHandlers): () => void {
    const es = new EventSource(this.base + "/api/stream");
    es.onopen = h.open;
    es.onerror = h.error;
    const on = <K extends keyof StreamHandlers>(name: K) =>
      es.addEventListener(name, (e) => (h[name] as (d: unknown) => void)(JSON.parse((e as MessageEvent).data)));
    on("msg");
    on("node");
    on("position");
    on("alert");
    return () => es.close();
  }
}
