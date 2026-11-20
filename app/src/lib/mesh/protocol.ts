// Protocolo cliente de Meshtastic (API "phone"): el teléfono escribe mensajes
// ToRadio y lee FromRadio. Sobre Bluetooth cada lectura/escritura es un
// protobuf completo, sin encabezados de trama.
import { create, fromBinary, toBinary } from "@bufbuild/protobuf";
import { Mesh, Portnums, Telemetry } from "@meshtastic/protobufs";
import { BROADCAST, type RadioEvents } from "./types";

/** Transporte de bytes crudo (Bluetooth hoy; serie o TCP se pueden agregar). */
export interface ByteTransport {
  open(onBytes: (b: Uint8Array) => void, onClosed: (reason: string) => void): Promise<void>;
  write(bytes: Uint8Array): Promise<void>;
  close(): Promise<void>;
}

const now = () => Math.floor(Date.now() / 1000);
const randomId = () => (crypto.getRandomValues(new Uint32Array(1))[0] >>> 0) || 1;
const decoder = new TextDecoder();
const encoder = new TextEncoder();

export class MeshProtocol {
  private transport: ByteTransport;
  private ev: RadioEvents;
  private configId = randomId();

  constructor(transport: ByteTransport, events: RadioEvents) {
    this.transport = transport;
    this.ev = events;
  }

  async start(): Promise<void> {
    this.ev.status("conectando");
    await this.transport.open(this.onBytes, (reason) => this.ev.status("desconectado", reason));
    this.ev.status("configurando");
    // Pide al nodo su información, la lista de nodos conocidos y la configuración.
    await this.write({ case: "wantConfigId", value: this.configId });
  }

  async stop(): Promise<void> {
    try {
      await this.write({ case: "disconnect", value: true });
    } catch {
      /* el enlace puede estar caído */
    }
    await this.transport.close();
    this.ev.status("desconectado", "usuario");
  }

  async sendText(text: string, to: number = BROADCAST, channel = 0): Promise<number> {
    const id = randomId();
    await this.sendData(Portnums.PortNum.TEXT_MESSAGE_APP, encoder.encode(text), to, channel, true, id);
    return id;
  }

  async sendPosition(lat: number, lon: number, alt?: number): Promise<void> {
    const pos = create(Mesh.PositionSchema, {
      latitudeI: Math.round(lat * 1e7),
      longitudeI: Math.round(lon * 1e7),
      altitude: alt != null ? Math.round(alt) : undefined,
      time: now(),
    });
    await this.sendData(Portnums.PortNum.POSITION_APP, toBinary(Mesh.PositionSchema, pos), BROADCAST, 0, false);
  }

  // --- internos -------------------------------------------------------
  private async sendData(portnum: Portnums.PortNum, payload: Uint8Array, to: number, channel: number,
                         wantAck: boolean, id = randomId()): Promise<void> {
    const data = create(Mesh.DataSchema, { portnum, payload });
    const packet = create(Mesh.MeshPacketSchema, {
      id, to, channel, wantAck, payloadVariant: { case: "decoded", value: data },
    });
    await this.write({ case: "packet", value: packet });
  }

  private async write(variant: Mesh.ToRadio["payloadVariant"]): Promise<void> {
    const msg = create(Mesh.ToRadioSchema, { payloadVariant: variant });
    await this.transport.write(toBinary(Mesh.ToRadioSchema, msg));
  }

  private onBytes = (bytes: Uint8Array) => {
    let fr: Mesh.FromRadio;
    try {
      fr = fromBinary(Mesh.FromRadioSchema, bytes);
    } catch {
      return; // trama corrupta: se ignora
    }
    const v = fr.payloadVariant;
    switch (v.case) {
      case "myInfo":
        this.ev.myNode(v.value.myNodeNum);
        break;
      case "nodeInfo": {
        const n = v.value;
        const pos = n.position;
        this.ev.node({
          num: n.num,
          longName: n.user?.longName || undefined,
          shortName: n.user?.shortName || undefined,
          lat: pos?.latitudeI ? pos.latitudeI * 1e-7 : undefined,
          lon: pos?.longitudeI ? pos.longitudeI * 1e-7 : undefined,
          posTime: pos?.time || undefined,
          battery: n.deviceMetrics?.batteryLevel,
          lastHeard: n.lastHeard || undefined,
        });
        break;
      }
      case "configCompleteId":
        if (v.value === this.configId) this.ev.status("conectado");
        break;
      case "packet":
        this.onPacket(v.value);
        break;
    }
  };

  private onPacket(p: Mesh.MeshPacket) {
    if (p.payloadVariant.case !== "decoded") return; // cifrado con una clave que no tenemos
    const d = p.payloadVariant.value;
    const ts = p.rxTime || now();
    try {
      switch (d.portnum) {
        case Portnums.PortNum.TEXT_MESSAGE_APP:
          this.ev.text({ packetId: p.id, from: p.from, to: p.to, text: decoder.decode(d.payload), ts });
          break;
        case Portnums.PortNum.POSITION_APP: {
          const pos = fromBinary(Mesh.PositionSchema, d.payload);
          if (pos.latitudeI && pos.longitudeI) {
            this.ev.node({ num: p.from, lat: pos.latitudeI * 1e-7, lon: pos.longitudeI * 1e-7,
                           posTime: pos.time || ts });
          }
          break;
        }
        case Portnums.PortNum.NODEINFO_APP: {
          const user = fromBinary(Mesh.UserSchema, d.payload);
          this.ev.node({ num: p.from, longName: user.longName, shortName: user.shortName });
          break;
        }
        case Portnums.PortNum.TELEMETRY_APP: {
          const t = fromBinary(Telemetry.TelemetrySchema, d.payload);
          if (t.variant.case === "deviceMetrics") this.ev.node({ num: p.from, battery: t.variant.value.batteryLevel });
          break;
        }
        case Portnums.PortNum.ROUTING_APP: {
          const r = fromBinary(Mesh.RoutingSchema, d.payload);
          if (r.variant.case === "errorReason" && d.requestId) {
            const ok = r.variant.value === Mesh.Routing_Error.NONE;
            this.ev.ack(d.requestId, ok, ok ? undefined : Mesh.Routing_Error[r.variant.value]);
          }
          break;
        }
      }
    } catch {
      /* carga útil mal formada: se ignora */
    }
    this.ev.node({ num: p.from, lastHeard: ts });
  }
}
