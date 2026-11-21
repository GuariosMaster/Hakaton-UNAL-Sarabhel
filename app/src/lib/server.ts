// Cliente del servidor del puesto de mando (server/sarabhel/dashboard.py).
// Se usa en el modo Mando y en Campo → Puesto de mando, con el teléfono en el Wi-Fi del puesto.
// Todas las rutas (salvo login y config) piden el token de sesión.
import type { Priority } from "./priority";

export interface ServerNode {
  node_id: string;
  long_name?: string | null;
  short_name?: string | null;
  lat?: number | null;
  lon?: number | null;
  pos_ts?: number | null;
  battery?: number | null;
  voltage?: number | null;
  panel_v?: number | null;
  rssi?: number | null;
  energy_ts?: number | null;
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

export type AlertState = "nueva" | "en_atencion" | "atendida";

export interface ServerAlert {
  id: number;
  type: "mensaje_critico" | "zona_riesgo" | "bateria_baja";
  node_id?: string | null;
  from_node?: string;
  estado: AlertState;
  equipo?: string | null;
  nota?: string | null;
  long_name?: string | null;
  text?: string;
  zone?: string;
  battery?: number;
  voltage?: number | null;
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
  alert_update: (a: ServerAlert) => void;
}

export type Role = "admin" | "mando" | "socorrista";

export interface UserInfo {
  usuario: string;
  nombre: string;
  rol: Role;
  equipo?: string | null;
  activo?: number;
  pin_inicial?: number;
}

export interface LoginResult extends UserInfo {
  token: string;
  expira: number;
}

/** Error HTTP con el código, para distinguir "sin red" de "PIN incorrecto". */
export class HttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function normalizeUrl(url: string): string {
  let base = url.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//.test(base)) base = "http://" + base;
  return base;
}

export class ServerClient {
  readonly base: string;
  private token?: string;

  constructor(baseUrl: string, token?: string) {
    this.base = normalizeUrl(baseUrl);
    this.token = token;
  }

  private async req<T>(method: string, path: string, body?: unknown, timeoutMs = 8000): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const r = await fetch(this.base + path, {
      method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const b = await r.json();
        detail = Array.isArray(b.detail) ? b.detail.map((d: { msg: string }) => d.msg).join("; ") : b.detail || detail;
      } catch { /* sin cuerpo JSON */ }
      throw new HttpError(r.status, detail);
    }
    return r.json() as Promise<T>;
  }

  // --- sesión ---
  login(usuario: string, pin: string) {
    return this.req<LoginResult>("POST", "/api/auth/login", { usuario, pin }, 6000);
  }
  logout() { return this.req<{ status: string }>("POST", "/api/auth/logout"); }
  me() { return this.req<UserInfo>("GET", "/api/auth/me"); }
  changePin(actual: string, nuevo: string) {
    return this.req<{ status: string }>("POST", "/api/auth/pin", { actual, nuevo });
  }

  // --- usuarios (administrador) ---
  users() { return this.req<UserInfo[]>("GET", "/api/users"); }
  createUser(u: { usuario: string; nombre: string; rol: Role; pin: string; equipo?: string | null }) {
    return this.req<UserInfo>("POST", "/api/users", u);
  }
  updateUser(usuario: string, changes: Partial<{ nombre: string; rol: Role; equipo: string; activo: boolean; pin: string }>) {
    return this.req<UserInfo>("PATCH", `/api/users/${encodeURIComponent(usuario)}`, changes);
  }
  deleteUser(usuario: string) {
    return this.req<{ status: string }>("DELETE", `/api/users/${encodeURIComponent(usuario)}`);
  }

  // --- datos ---
  config() {
    return this.req<{
      tile_url: string; center: [number, number]; max_text_bytes: number;
      energy?: { battery_wh: number; consumption_w: number; dod: number; low_pct: number };
    }>("GET", "/api/config");
  }
  nodes() { return this.req<ServerNode[]>("GET", "/api/nodes"); }
  messages(limit = 100) { return this.req<ServerMessage[]>("GET", `/api/messages?limit=${limit}`); }
  zones() { return this.req<GeoJSON.FeatureCollection>("GET", "/api/zones"); }
  alerts(limit = 100) { return this.req<ServerAlert[]>("GET", `/api/alerts?limit=${limit}`); }

  updateAlert(id: number, changes: { estado?: AlertState; equipo?: string; nota?: string }) {
    return this.req<ServerAlert>("PATCH", `/api/alerts/${id}`, changes);
  }

  async send(text: string, to?: string | null): Promise<void> {
    await this.req("POST", "/api/send", { text, to: to || null });
  }

  // --- Teléfono como nodo por Wi-Fi (Campo → Puesto de mando) ---
  deviceHello(nodeId: string, longName: string, shortName?: string) {
    return this.req<{ status: string }>("POST", "/api/device/hello",
      { node_id: nodeId, long_name: longName, short_name: shortName });
  }

  deviceText(nodeId: string, text: string, to?: string | null, fix?: { lat: number; lon: number }) {
    return this.req<{ packet_id: number }>("POST", "/api/device/text",
      { node_id: nodeId, text, to: to || null, lat: fix?.lat, lon: fix?.lon });
  }

  devicePosition(nodeId: string, lat: number, lon: number, alt?: number) {
    return this.req<{ status: string }>("POST", "/api/device/position", { node_id: nodeId, lat, lon, alt });
  }

  /** Eventos en vivo (SSE). EventSource no admite cabeceras: el token va en la URL. */
  stream(h: StreamHandlers): () => void {
    const es = new EventSource(`${this.base}/api/stream?token=${encodeURIComponent(this.token ?? "")}`);
    es.onopen = h.open;
    es.onerror = h.error;
    const on = <K extends keyof StreamHandlers>(name: K) =>
      es.addEventListener(name, (e) => (h[name] as (d: unknown) => void)(JSON.parse((e as MessageEvent).data)));
    on("msg");
    on("node");
    on("position");
    on("alert");
    on("alert_update");
    return () => es.close();
  }
}
