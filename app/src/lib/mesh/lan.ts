// "Puesto de mando (Wi-Fi)": el teléfono se conecta a la red del puesto de mando y actúa
// como un nodo más a través del servidor, que reparte sus mensajes a los demás teléfonos,
// al dashboard y, si son para un nodo de albergue, los transmite por radio FSK.
// Sirve para probar la app entre varios teléfonos sin hardware y para quien esté cerca del puesto.
import { ServerClient, type ServerNode } from "../server";
import {
  BROADCAST, COMMAND_NUM, idToNum, numToId, type Fix, type MeshNode, type RadioEvents, type RadioLink,
} from "./types";

export interface LanIdentity {
  id: string; // "!a1b2c3d4"
  longName: string;
  shortName: string;
}

function fromServer(n: ServerNode): (Partial<MeshNode> & { num: number }) | undefined {
  const num = idToNum(n.node_id);
  if (num === undefined) return undefined;
  return {
    num,
    longName: n.long_name ?? undefined,
    shortName: n.short_name ?? undefined,
    lat: n.lat ?? undefined,
    lon: n.lon ?? undefined,
    posTime: n.pos_ts ?? undefined,
    battery: n.battery ?? undefined,
    voltage: n.voltage ?? undefined,
    panelV: n.panel_v ?? undefined,
    lastHeard: n.last_heard ?? undefined,
  };
}

export class LanRadio implements RadioLink {
  readonly kind = "red-local" as const;
  private ev: RadioEvents;
  private client: ServerClient;
  private me: LanIdentity;
  private closeStream?: () => void;

  constructor(events: RadioEvents, url: string, identity: LanIdentity) {
    this.ev = events;
    this.client = new ServerClient(url);
    this.me = identity;
  }

  async connect(): Promise<void> {
    this.ev.status("conectando");
    const myNum = idToNum(this.me.id)!;
    try {
      await this.client.deviceHello(this.me.id, this.me.longName, this.me.shortName);
    } catch (e) {
      throw new Error(`No se pudo conectar con ${this.client.base}: ${e instanceof Error ? e.message : e}`);
    }
    this.ev.status("configurando");
    this.ev.myNode(myNum);
    this.ev.node({ num: myNum, longName: this.me.longName, shortName: this.me.shortName,
                   lastHeard: Math.floor(Date.now() / 1000) });
    this.ev.node({ num: COMMAND_NUM, longName: "Puesto de mando", shortName: "MAND" });
    for (const n of await this.client.nodes()) {
      const node = fromServer(n);
      if (node && node.num !== COMMAND_NUM) this.ev.node(node);
    }

    this.closeStream = this.client.stream({
      open: () => this.ev.status("conectado"),
      error: () => this.ev.status("conectando", "Reconectando con el servidor…"),
      msg: (m) => {
        if (m.from_node === this.me.id) return; // eco de mi propio mensaje
        const to = m.to_node && m.to_node !== "^all" ? m.to_node : "^all";
        if (to !== "^all" && to !== this.me.id) return; // mensaje directo para otro nodo
        const from = idToNum(m.from_node);
        if (from === undefined) return;
        this.ev.text({ packetId: m.id, from, to: to === "^all" ? BROADCAST : myNum, text: m.text, ts: m.ts });
      },
      node: (n) => {
        const node = fromServer(n);
        if (node && node.num !== COMMAND_NUM) this.ev.node(node);
      },
      position: (p) => {
        const num = idToNum(p.node_id);
        if (num !== undefined) this.ev.node({ num, lat: p.lat, lon: p.lon, posTime: p.ts, lastHeard: p.ts });
      },
      alert: () => {},
      alert_update: () => {},
    });
  }

  async disconnect(): Promise<void> {
    this.closeStream?.();
    this.closeStream = undefined;
    this.ev.status("desconectado", "usuario");
  }

  async sendText(text: string, to: number = BROADCAST, fix?: Fix): Promise<number> {
    const dest = to === BROADCAST ? null : numToId(to);
    const { packet_id } = await this.client.deviceText(this.me.id, text, dest, fix);
    // El servidor ya lo aceptó: se confirma justo después de que la app registre el id.
    setTimeout(() => this.ev.ack(packet_id, true), 0);
    return packet_id;
  }

  async sendPosition(lat: number, lon: number, alt?: number): Promise<void> {
    await this.client.devicePosition(this.me.id, lat, lon, alt);
  }
}
