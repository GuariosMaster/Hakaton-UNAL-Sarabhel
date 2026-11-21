// Conexión al nodo de albergue (ESP32 + RFM69HCW) por su red Wi-Fi "Emergencia …".
// El nodo crea su propia red sin internet y expone una API HTTP (firmware/src/nodo):
//   GET  /api/estado               nombre, dirección y energía del nodo
//   GET  /api/mensajes?desde=SEQ   mensajes recibidos por radio
//   POST /api/mensaje              {"msg","dest","lat","lon"} -> se transmite por radio FSK
//   POST /api/posicion             {"lat","lon"}
import { BROADCAST, COMMAND_NUM, type Fix, type RadioEvents, type RadioLink } from "./types";

interface EstadoNodo {
  nodo: number;
  nombre: string;
  bat: number;
  panel: number;
  carga: number;
  conectados: number;
  max_texto: number;
}

interface MensajeNodo {
  seq: number;
  de: number;
  para: number;
  propio: boolean;
  hace: number;
  msg: string;
}

const POLL_MS = 3000;
const now = () => Math.floor(Date.now() / 1000);

export class AlbergueRadio implements RadioLink {
  readonly kind = "albergue" as const;
  private ev: RadioEvents;
  private base: string;
  private timer?: ReturnType<typeof setInterval>;
  private lastSeq = 0;
  private address = 0;
  private failures = 0;
  private polling = false;

  constructor(events: RadioEvents, url: string) {
    this.ev = events;
    let base = url.trim().replace(/\/+$/, "");
    if (!/^https?:\/\//.test(base)) base = "http://" + base;
    this.base = base;
  }

  private async req<T>(path: string, body?: unknown): Promise<T> {
    const r = await fetch(this.base + path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(body ? 15000 : 6000), // enviar espera la confirmación por radio
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error((data as { error?: string }).error || `${r.status} ${r.statusText}`);
    return data as T;
  }

  async connect(): Promise<void> {
    this.ev.status("conectando");
    let estado: EstadoNodo;
    try {
      estado = await this.req<EstadoNodo>("/api/estado");
    } catch {
      throw new Error(
        `No se encontró el nodo en ${this.base}. Conéctate a la red Wi‑Fi "Emergencia …" del albergue ` +
        "y apaga los datos móviles.",
      );
    }
    this.ev.status("configurando");
    this.address = estado.nodo;
    this.ev.myNode(estado.nodo);
    this.updateNode(estado);
    this.ev.node({ num: COMMAND_NUM, longName: "Puesto de mando", shortName: "MAND" });

    // Solo mensajes nuevos desde ahora (el historial del nodo ya se mostró en su portal).
    const inicial = await this.req<{ ultimo: number }>("/api/mensajes?desde=0");
    this.lastSeq = inicial.ultimo;
    this.ev.status("conectado");
    this.timer = setInterval(() => void this.poll(), POLL_MS);
  }

  async disconnect(): Promise<void> {
    clearInterval(this.timer);
    this.timer = undefined;
    this.ev.status("desconectado", "usuario");
  }

  async sendText(text: string, to: number = BROADCAST, fix?: Fix): Promise<number> {
    // Desde un nodo, "todos" significa el puesto de mando: él lo reparte al resto de la red.
    const dest = to === BROADCAST || to > 254 ? COMMAND_NUM : to;
    const isSos = text.toUpperCase().startsWith("SOS");
    const payload = {
      tipo: isSos ? "sos" : "texto",
      mensaje: text,
      destino: dest,
      latitud: fix?.lat ?? null,
      longitud: fix?.lon ?? null,
      // Alias para máxima compatibilidad:
      msg: text,
      dest,
      lat: fix?.lat ?? null,
      lon: fix?.lon ?? null,
    };
    const r = await this.req<{ ok: boolean; seq: number }>("/api/mensaje", payload);
    setTimeout(() => this.ev.ack(r.seq, true), 0);
    return r.seq;
  }

  async sendPosition(lat: number, lon: number): Promise<void> {
    await this.req("/api/posicion", { latitud: lat, longitud: lon, lat, lon });
  }

  private updateNode(e: EstadoNodo) {
    this.ev.node({ num: e.nodo, longName: e.nombre, battery: e.carga, voltage: e.bat, panelV: e.panel,
                   lastHeard: now() });
  }

  private async poll() {
    if (this.polling) return;
    this.polling = true;
    try {
      const r = await this.req<{ ultimo: number; mensajes: MensajeNodo[] }>(`/api/mensajes?desde=${this.lastSeq}`);
      for (const m of r.mensajes) {
        if (m.propio) continue; // enviados desde este nodo (por la app o por el portal)
        this.ev.node({ num: m.de, lastHeard: now() - m.hace });
        this.ev.text({ packetId: m.seq, from: m.de, to: m.para === this.address ? this.address : BROADCAST,
                       text: m.msg, ts: now() - m.hace });
      }
      this.lastSeq = r.ultimo;
      if (this.failures > 0) this.ev.status("conectado");
      this.failures = 0;
      if (Math.random() < 0.2) this.updateNode(await this.req<EstadoNodo>("/api/estado"));
    } catch {
      this.failures++;
      if (this.failures >= 2) this.ev.status("conectando", "Sin respuesta del nodo; reintentando…");
    } finally {
      this.polling = false;
    }
  }
}
