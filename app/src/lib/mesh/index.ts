import { BleTransport } from "./ble";
import { LanRadio, type LanIdentity } from "./lan";
import { MeshProtocol } from "./protocol";
import { SimRadio } from "./sim";
import type { RadioEvents, RadioLink } from "./types";

class BluetoothRadio implements RadioLink {
  readonly kind = "bluetooth" as const;
  private proto: MeshProtocol;

  constructor(events: RadioEvents) {
    this.proto = new MeshProtocol(new BleTransport(), events);
  }
  connect() { return this.proto.start(); }
  disconnect() { return this.proto.stop(); }
  sendText(text: string, to?: number) { return this.proto.sendText(text, to); }
  sendPosition(lat: number, lon: number, alt?: number) { return this.proto.sendPosition(lat, lon, alt); }
}

export interface RadioOptions {
  serverUrl: string;
  identity: LanIdentity;
}

export function createRadio(kind: RadioLink["kind"], events: RadioEvents, opts: RadioOptions): RadioLink {
  if (kind === "bluetooth") return new BluetoothRadio(events);
  if (kind === "red-local") return new LanRadio(events, opts.serverUrl, opts.identity);
  return new SimRadio(events);
}

export type { LanIdentity };
export * from "./types";
