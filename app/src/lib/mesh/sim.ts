// Modo demo: simula estar conectado a un nodo de albergue de la red FSK 915 MHz.
// Imita lo que haría el nodo real: otros nodos con su energía solar, mensajes que llegan
// y respuestas del puesto de mando. Datos ficticios alrededor de Manizales.
import { BROADCAST, COMMAND_NUM, type RadioEvents, type RadioLink } from "./types";

const ME = 2; // el nodo de albergue al que "está conectado" el teléfono
const NODES = [
  { num: COMMAND_NUM, longName: "Puesto de mando UNAL", shortName: "MAND", lat: 5.0556, lon: -75.4930 },
  { num: 3, longName: "Albergue Chipre", shortName: "CHIP", lat: 5.0745, lon: -75.526 },
  { num: 4, longName: "Ladera Aranjuez", shortName: "ARAN", lat: 5.059, lon: -75.4985 },
  { num: 5, longName: "Brigada La Enea", shortName: "ENEA", lat: 5.0315, lon: -75.463 },
  { num: 6, longName: "Puesto San José", shortName: "SJOS", lat: 5.07, lon: -75.5195 },
];
const CHATTER = [
  "Todos bien en punto de encuentro",
  "Necesitamos agua para 30 personas",
  "Grieta en la via, evacuando",
  "Llegamos al albergue, 12 personas",
  "Recibido, quedamos atentos",
];

const now = () => Math.floor(Date.now() / 1000);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function energy() {
  const h = new Date().getHours() + new Date().getMinutes() / 60;
  const sun = h >= 6 && h <= 18 ? Math.max(0, Math.sin((Math.PI * (h - 6)) / 12)) : 0;
  const battery = 40 + Math.floor(Math.random() * 55);
  return { battery, voltage: +(12 + (battery / 100) * 1.6).toFixed(2), panelV: +(sun * (17 + Math.random() * 2)).toFixed(1) };
}

export class SimRadio implements RadioLink {
  readonly kind = "simulador" as const;
  private ev: RadioEvents;
  private timer?: ReturnType<typeof setInterval>;
  private nextId = 1000;

  constructor(events: RadioEvents) {
    this.ev = events;
  }

  async connect(): Promise<void> {
    this.ev.status("conectando");
    await sleep(600);
    this.ev.status("configurando");
    this.ev.myNode(ME);
    this.ev.node({ num: ME, longName: "Albergue Coliseo (demo)", shortName: "COLI", ...energy(), lastHeard: now() });
    for (const n of NODES) {
      this.ev.node({ ...n, ...(n.num === COMMAND_NUM ? {} : energy()), posTime: now(), lastHeard: now() });
    }
    await sleep(400);
    this.ev.status("conectado");
    this.timer = setInterval(() => this.tick(), 9000);
  }

  async disconnect(): Promise<void> {
    clearInterval(this.timer);
    this.ev.status("desconectado", "usuario");
  }

  async sendText(text: string, to: number = BROADCAST): Promise<number> {
    const id = ++this.nextId;
    setTimeout(() => this.ev.ack(id, true), 900 + Math.random() * 800);
    if (/\bsos\b/i.test(text)) {
      setTimeout(() => this.ev.text({ packetId: ++this.nextId, from: COMMAND_NUM, to: ME, ts: now(),
        text: "Recibido. Brigada en camino" }), 4000);
    } else if (to !== BROADCAST && to !== COMMAND_NUM) {
      setTimeout(() => this.ev.text({ packetId: ++this.nextId, from: to, to: ME, ts: now(), text: "Recibido 👍" }), 3500);
    }
    return id;
  }

  async sendPosition(lat: number, lon: number): Promise<void> {
    this.ev.node({ num: ME, lat, lon, posTime: now(), lastHeard: now() });
  }

  private tick() {
    const n = NODES[1 + Math.floor(Math.random() * (NODES.length - 1))];
    if (Math.random() < 0.6) {
      n.lat += (Math.random() - 0.5) * 0.002;
      n.lon += (Math.random() - 0.5) * 0.002;
      this.ev.node({ num: n.num, lat: n.lat, lon: n.lon, posTime: now(), lastHeard: now(), ...energy() });
    } else {
      this.ev.text({ packetId: ++this.nextId, from: n.num, to: BROADCAST, ts: now(),
                     text: CHATTER[Math.floor(Math.random() * CHATTER.length)] });
    }
  }
}
