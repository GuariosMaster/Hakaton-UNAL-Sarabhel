import { BleTransport } from "./ble";
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

export function createRadio(kind: RadioLink["kind"], events: RadioEvents): RadioLink {
  return kind === "bluetooth" ? new BluetoothRadio(events) : new SimRadio(events);
}

export * from "./types";
