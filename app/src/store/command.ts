// Estado del modo Mando: conexión con el servidor local del puesto de mando.
import { create } from "zustand";
import {
  ServerClient, type ServerAlert, type ServerMessage, type ServerNode,
} from "../lib/server";
import { load, save } from "../lib/util";

type Status = "desconectado" | "conectando" | "conectado" | "error";

interface CommandState {
  url: string;
  status: Status;
  error?: string;
  tileUrl?: string;
  nodes: Record<string, ServerNode>;
  messages: ServerMessage[];
  alerts: ServerAlert[];
  zones?: GeoJSON.FeatureCollection;
  connect: (url: string) => Promise<void>;
  disconnect: () => void;
  send: (text: string, to?: string | null) => Promise<void>;
}

// 192.168.137.1 es la IP del portátil cuando comparte su Wi-Fi como zona con cobertura en Windows.
const DEFAULT_URL = "http://192.168.137.1:8080";
let client: ServerClient | undefined;
let closeStream: (() => void) | undefined;

export const useCommand = create<CommandState>()((set) => ({
  url: load("mando.url", DEFAULT_URL),
  status: "desconectado",
  nodes: {},
  messages: [],
  alerts: [],

  connect: async (url) => {
    closeStream?.();
    save("mando.url", url);
    client = new ServerClient(url);
    set({ url, status: "conectando", error: undefined });
    try {
      const [cfg, nodes, messages, zones] = await Promise.all([
        client.config(), client.nodes(), client.messages(150), client.zones(),
      ]);
      const alerts: ServerAlert[] = messages
        .filter((m) => m.priority === "critico" && m.direction === "in")
        .slice(0, 30)
        .map((m) => ({ type: "mensaje_critico", from_node: m.from_node, long_name: m.long_name,
                       text: m.text, lat: m.lat, lon: m.lon, ts: m.ts }));
      set({
        tileUrl: cfg.tile_url,
        nodes: Object.fromEntries(nodes.map((n) => [n.node_id, n])),
        messages,
        alerts,
        zones,
      });
      closeStream = client.stream({
        open: () => set({ status: "conectado", error: undefined }),
        error: () => set({ status: "error", error: "Se perdió la conexión con el servidor; reintentando…" }),
        msg: (m) => set((s) => ({ messages: [m, ...s.messages].slice(0, 300) })),
        node: (n) => set((s) => ({ nodes: { ...s.nodes, [n.node_id]: { ...s.nodes[n.node_id], ...n } } })),
        position: (p) =>
          set((s) => ({
            nodes: {
              ...s.nodes,
              [p.node_id]: { ...s.nodes[p.node_id], node_id: p.node_id, lat: p.lat, lon: p.lon,
                             pos_ts: p.ts, last_heard: p.ts, risk_zone: p.risk_zone },
            },
          })),
        alert: (a) =>
          set((s) => ({
            alerts: [a, ...s.alerts].slice(0, 50),
            nodes: a.type === "mensaje_critico"
              ? { ...s.nodes, [a.from_node]: { ...s.nodes[a.from_node], node_id: a.from_node, alert_ts: a.ts } }
              : s.nodes,
          })),
      });
    } catch (e) {
      client = undefined;
      set({ status: "error", error: `No se pudo conectar con ${url}: ${e instanceof Error ? e.message : e}` });
    }
  },

  disconnect: () => {
    closeStream?.();
    closeStream = undefined;
    client = undefined;
    set({ status: "desconectado" });
  },

  send: async (text, to) => {
    if (!client) throw new Error("No hay conexión con el servidor");
    await client.send(text, to);
  },
}));

export const serverNodeName = (nodes: Record<string, ServerNode>, id?: string | null) => {
  if (!id || id === "^all") return "Todos";
  if (id === "puesto-mando") return "Puesto de mando";
  const n = nodes[id];
  return n?.long_name || n?.short_name || id;
};
