import type { Priority } from "../priority";

export type LinkStatus = "desconectado" | "conectando" | "configurando" | "conectado";

export interface MeshNode {
  num: number;
  id: string; // formato Meshtastic "!a1b2c3d4"
  longName?: string;
  shortName?: string;
  lat?: number;
  lon?: number;
  posTime?: number; // epoch s
  battery?: number;
  lastHeard?: number; // epoch s
}

export type DeliveryStatus = "enviando" | "en-red" | "entregado" | "fallo";

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

/** Eventos que cualquier enlace de radio (Bluetooth o simulado) entrega a la app. */
export interface RadioEvents {
  status: (s: LinkStatus, detail?: string) => void;
  myNode: (num: number) => void;
  node: (n: Partial<MeshNode> & { num: number }) => void;
  text: (m: { packetId: number; from: number; to: number; text: string; ts: number }) => void;
  ack: (packetId: number, ok: boolean, reason?: string) => void;
}

export interface RadioLink {
  readonly kind: "bluetooth" | "simulador";
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  /** Devuelve el id de paquete para seguir su confirmación. */
  sendText(text: string, to?: number): Promise<number>;
  sendPosition(lat: number, lon: number, alt?: number): Promise<void>;
}

export const BROADCAST = 0xffffffff;

export const numToId = (num: number) => "!" + (num >>> 0).toString(16).padStart(8, "0");
export const idToNum = (id: string) => parseInt(id.replace(/^!/, ""), 16) >>> 0;
