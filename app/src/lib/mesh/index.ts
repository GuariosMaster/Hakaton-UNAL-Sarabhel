import { AlbergueRadio } from "./albergue";
import { LanRadio, type LanIdentity } from "./lan";
import { SimRadio } from "./sim";
import type { RadioEvents, RadioLink } from "./types";

export interface RadioOptions {
  /** Dirección del nodo de albergue en su red Wi-Fi (por defecto http://192.168.4.1). */
  nodeUrl: string;
  /** Servidor del puesto de mando y nombre de este teléfono (conexión "red-local"). */
  serverUrl: string;
  identity: LanIdentity;
}

export function createRadio(kind: RadioLink["kind"], events: RadioEvents, opts: RadioOptions): RadioLink {
  if (kind === "albergue") return new AlbergueRadio(events, opts.nodeUrl);
  if (kind === "red-local") return new LanRadio(events, opts.serverUrl, opts.identity);
  return new SimRadio(events);
}

export type { LanIdentity };
export * from "./types";
