// Estado del modo Campo: conexión con el nodo de albergue (o el puesto de mando), nodos, mensajes y GPS.
import { create } from "zustand";
import {
  BROADCAST, createRadio, idToNum, numToId,
  type ChatMessage, type LinkStatus, type MeshNode, type RadioLink,
} from "../lib/mesh";
import { classify } from "../lib/priority";
import { getFix, load, now, save, type Fix } from "../lib/util";

type Kind = RadioLink["kind"];

interface FieldState {
  kind: Kind;
  /** Dirección del nodo de albergue en su red Wi-Fi. */
  nodeUrl: string;
  setNodeUrl: (url: string) => void;
  /** Para la conexión "Puesto de mando (Wi-Fi)": servidor y nombre de este teléfono. */
  serverUrl: string;
  deviceName: string;
  deviceId: string;
  setLanSettings: (serverUrl: string, deviceName: string) => void;
  status: LinkStatus;
  detail?: string;
  myNum?: number;
  nodes: Record<number, MeshNode>;
  messages: ChatMessage[];
  fix?: Fix;
  gpsError?: string;
  connect: (kind: Kind) => Promise<void>;
  disconnect: () => Promise<void>;
  send: (text: string, to?: string) => Promise<void>;
  sendEmergency: (text: string) => Promise<void>;
  locate: () => Promise<Fix | undefined>;
}

const MAX_MESSAGES = 300;
let radio: RadioLink | undefined;

// Identificador estable de este teléfono en la red ("!" + 8 hex), distinto de los nodos de radio.
function deviceId(): string {
  const saved = load<string | null>("campo.idDispositivo", null);
  if (saved && /^![0-9a-f]{8}$/.test(saved)) return saved;
  const id = "!" + Array.from(crypto.getRandomValues(new Uint8Array(4)), (b) => b.toString(16).padStart(2, "0")).join("");
  save("campo.idDispositivo", id);
  return id;
}

const shortFrom = (name: string) =>
  (name.split(/\s+/).map((w) => w[0]).join("") || name).slice(0, 4).toUpperCase();

export const useField = create<FieldState>()((set, get) => {
  const addMessage = (m: ChatMessage) =>
    set((s) => {
      const messages = [...s.messages, m].slice(-MAX_MESSAGES);
      save("campo.mensajes", messages);
      return { messages };
    });

  const updateMessage = (packetId: number, patch: Partial<ChatMessage>) =>
    set((s) => {
      const messages = s.messages.map((m) => (m.packetId === packetId && m.mine ? { ...m, ...patch } : m));
      save("campo.mensajes", messages);
      return { messages };
    });

  const sendRaw = async (text: string, to: string, fix?: Fix) => {
    if (!radio || get().status !== "conectado") throw new Error("Conéctate primero al Wi‑Fi del albergue");
    const key = crypto.randomUUID();
    addMessage({ key, from: "yo", to, text, ts: now(), priority: classify(text), mine: true,
                 status: "enviando", lat: fix?.lat, lon: fix?.lon });
    try {
      const packetId = await radio.sendText(text, to === "^all" ? BROADCAST : idToNum(to) ?? BROADCAST, fix);
      set((s) => ({ messages: s.messages.map((m) => (m.key === key ? { ...m, packetId } : m)) }));
    } catch (e) {
      set((s) => ({ messages: s.messages.map((m) => (m.key === key ? { ...m, status: "fallo" } : m)) }));
      throw e;
    }
  };

  const id = deviceId();

  return {
    kind: (() => {
      const k = load<string>("campo.tipo", "simulador");
      return (["albergue", "red-local", "simulador"].includes(k) ? k : "simulador") as Kind;
    })(),
    nodeUrl: load("campo.nodo", "http://192.168.4.1"),
    setNodeUrl: (nodeUrl) => {
      save("campo.nodo", nodeUrl);
      set({ nodeUrl });
    },
    serverUrl: load("campo.servidor", "http://192.168.137.1:8080"),
    deviceName: load("campo.nombre", `Teléfono ${id.slice(-4).toUpperCase()}`),
    deviceId: id,
    setLanSettings: (serverUrl, deviceName) => {
      save("campo.servidor", serverUrl);
      save("campo.nombre", deviceName);
      set({ serverUrl, deviceName });
    },
    status: "desconectado",
    nodes: {},
    messages: load<ChatMessage[]>("campo.mensajes", []),

    connect: async (kind) => {
      await radio?.disconnect().catch(() => {});
      save("campo.tipo", kind);
      set({ kind, detail: undefined, nodes: {}, myNum: undefined });
      radio = createRadio(kind, {
        status: (status, detail) => set({ status, detail }),
        myNode: (myNum) => set({ myNum }),
        node: (n) =>
          set((s) => {
            const prev = s.nodes[n.num] ?? { num: n.num, id: numToId(n.num) };
            const merged: MeshNode = { ...prev };
            for (const [k, v] of Object.entries(n)) if (v !== undefined) (merged as unknown as Record<string, unknown>)[k] = v;
            return { nodes: { ...s.nodes, [n.num]: merged } };
          }),
        text: (m) => {
          if (m.from === get().myNum) return; // eco de nuestro propio mensaje
          addMessage({ key: `rx-${m.packetId}-${m.from}`, packetId: m.packetId, from: numToId(m.from),
                       to: m.to === BROADCAST ? "^all" : numToId(m.to), text: m.text, ts: m.ts,
                       priority: classify(m.text), mine: false });
        },
        ack: (packetId, ok) => updateMessage(packetId, { status: ok ? "en-red" : "fallo" }),
      }, {
        nodeUrl: get().nodeUrl,
        serverUrl: get().serverUrl,
        identity: { id: get().deviceId, longName: get().deviceName, shortName: shortFrom(get().deviceName) },
      });
      try {
        await radio.connect();
      } catch (e) {
        set({ status: "desconectado", detail: e instanceof Error ? e.message : String(e) });
      }
    },

    disconnect: async () => {
      await radio?.disconnect().catch(() => {});
      radio = undefined;
      set({ status: "desconectado" });
    },

    send: (text, to = "^all") => sendRaw(text, to),

    /** SOS / mensaje rápido: toma la ubicación GPS y la envía junto con el texto (trama POS + MSG). */
    sendEmergency: async (text) => {
      const fix = await get().locate();
      await sendRaw(text, "^all", fix);
    },

    locate: async () => {
      try {
        const fix = await getFix();
        set({ fix, gpsError: undefined });
        return fix;
      } catch (e) {
        set({ gpsError: e instanceof Error ? e.message : "GPS no disponible" });
        return get().fix; // última ubicación conocida, si existe
      }
    },
  };
});

export const nodeLabel = (nodes: Record<number, MeshNode>, id: string) => {
  if (id === "^all") return "Todos";
  if (id === "yo") return "Yo";
  const num = idToNum(id);
  const n = num !== undefined ? nodes[num] : undefined;
  return n?.longName || n?.shortName || id;
};
