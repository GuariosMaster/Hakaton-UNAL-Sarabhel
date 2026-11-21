// Estado del modo Mando: conexión con el servidor local del puesto de mando.
import { create } from "zustand";
import {
  ServerClient, type AlertState, type ServerAlert, type ServerMessage, type ServerNode,
} from "../lib/server";
import type { Priority } from "../lib/priority";
import { load, notifyAlert, save } from "../lib/util";
import { useAuth } from "./auth";

type Status = "desconectado" | "conectando" | "conectado" | "error";

interface CommandState {
  url: string;
  status: Status;
  error?: string;
  tileUrl?: string;
  energyKit?: { battery_wh: number; consumption_w: number; dod: number; low_pct: number };
  nodes: Record<string, ServerNode>;
  messages: ServerMessage[];
  alerts: ServerAlert[];
  zones?: GeoJSON.FeatureCollection;
  connect: (url: string) => Promise<void>;
  disconnect: () => void;
  send: (text: string, to?: string | null) => Promise<void>;
  updateAlert: (id: number, changes: { estado?: AlertState; equipo?: string; nota?: string }) => Promise<void>;
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
    const token = useAuth.getState().session?.token;
    if (!token) {
      set({ url, status: "error", error: "Entraste sin conexión: vuelve a iniciar sesión conectado al Wi‑Fi del puesto de mando." });
      return;
    }
    client = new ServerClient(url, token);
    set({ url, status: "conectando", error: undefined });
    try {
      const [cfg, nodes, messages, zones, alerts] = await Promise.all([
        client.config(), client.nodes(), client.messages(150), client.zones(), client.alerts(100),
      ]);
      set({
        tileUrl: cfg.tile_url,
        energyKit: cfg.energy,
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
        alert: (a) => {
          if (a.estado === "nueva") notifyAlert();
          set((s) => {
            const node = a.from_node ?? a.node_id;
            return {
              alerts: [a, ...s.alerts.filter((x) => x.id !== a.id)].slice(0, 100),
              nodes: a.type === "mensaje_critico" && node
                ? { ...s.nodes, [node]: { ...s.nodes[node], node_id: node, alert_ts: a.ts } }
                : s.nodes,
            };
          });
        },
        alert_update: (a) => set((s) => ({ alerts: s.alerts.map((x) => (x.id === a.id ? { ...x, ...a } : x)) })),
        triage: (t) =>
          set((s) => ({
            messages: s.messages.map((m) =>
              m.id === t.message_id
                ? {
                    ...m,
                    priority: (t.prioridad as Priority) || m.priority,
                    ai_categoria: t.categoria,
                    ai_subcategoria: t.subcategoria,
                    ai_prioridad: t.prioridad,
                    ai_necesidades: t.necesidades,
                    ai_resumen: t.resumen,
                    ai_fuente: t.fuente,
                  }
                : m
            ),
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

  updateAlert: async (id, changes) => {
    if (!client) throw new Error("No hay conexión con el servidor");
    const row = await client.updateAlert(id, changes);
    set((s) => ({ alerts: s.alerts.map((x) => (x.id === row.id ? { ...x, ...row } : x)) }));
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
