import type { Priority } from "../priority";

export type LinkStatus = "desconectado" | "conectando" | "configurando" | "conectado";

export interface MeshNode {
  num: number;
  id: string; // "nodo-2" (radio FSK), "puesto-mando" o "!a1b2c3d4" (teléfono por Wi-Fi)
  longName?: string;
  shortName?: string;
  lat?: number;
  lon?: number;
  posTime?: number; // epoch s
  battery?: number; // % de carga
  voltage?: number; // V batería
  panelV?: number; // V panel solar
  lastHeard?: number; // epoch s
}

/** en-cola = escrito sin conexión; se envía solo al reconectar. */
export type DeliveryStatus = "en-cola" | "enviando" | "en-red" | "entregado" | "fallo";

export interface ChatMessage {
  key: string;
  packetId?: number;
  from: string; // id del nodo o "yo"
  to: string; // "^all" o id del nodo
  text: string;
  ts: number; // epoch s
  priority: Priority;
  mine: boolean;
  status?: DeliveryStatus;
  lat?: number;
  lon?: number;
}

/** Eventos que cualquier conexión (nodo de albergue, puesto de mando o demo) entrega a la app. */
export interface RadioEvents {
  status: (s: LinkStatus, detail?: string) => void;
  myNode: (num: number) => void;
  node: (n: Partial<MeshNode> & { num: number }) => void;
  text: (m: { packetId: number; from: number; to: number; text: string; ts: number }) => void;
  ack: (packetId: number, ok: boolean, reason?: string) => void;
}

export interface Fix {
  lat: number;
  lon: number;
}

export interface RadioLink {
  /** albergue = Wi-Fi del nodo ESP32 · red-local = Wi-Fi del puesto de mando · simulador = demo */
  readonly kind: "albergue" | "red-local" | "simulador";
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  /** Devuelve el id de paquete para seguir su confirmación. `fix` = ubicación GPS del teléfono. */
  sendText(text: string, to?: number, fix?: Fix): Promise<number>;
  sendPosition(lat: number, lon: number, alt?: number): Promise<void>;
}

export const BROADCAST = 0xffffffff;
/** Dirección RHMesh del gateway del puesto de mando. */
export const COMMAND_NUM = 1;

/**
 * Números internos de nodo y sus ids:
 *   1        -> "puesto-mando" (gateway)
 *   2..254   -> "nodo-N" (nodos de albergue por radio FSK)
 *   otros    -> "!xxxxxxxx" (teléfonos conectados por Wi-Fi al puesto de mando)
 */
export function numToId(num: number): string {
  if (num === COMMAND_NUM) return "puesto-mando";
  if (num >= 2 && num <= 254) return `nodo-${num}`;
  return "!" + (num >>> 0).toString(16).padStart(8, "0");
}

export function idToNum(id: string): number | undefined {
  if (id === "puesto-mando" || id === "nodo-1") return COMMAND_NUM;
  const radio = /^nodo-(\d{1,3})$/.exec(id);
  if (radio) {
    const n = Number(radio[1]);
    return n >= 1 && n <= 254 ? n : undefined;
  }
  if (/^![0-9a-f]{8}$/.test(id)) return parseInt(id.slice(1), 16) >>> 0;
  return undefined;
}
