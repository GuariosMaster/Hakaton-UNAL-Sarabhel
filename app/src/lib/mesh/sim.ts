// Radio simulada: permite usar y presentar la app sin el dispositivo físico.
// Imita lo que haría un nodo real: lista de nodos, posiciones, mensajes y
// confirmaciones de entrega. Datos ficticios alrededor de Manizales.
import { BROADCAST, type RadioEvents, type RadioLink } from "./types";

const ME = 0x5a0b00ff;
const COMMAND = 0x5a0b0000;
const NODES = [
  { num: COMMAND, longName: "Puesto de mando UNAL", shortName: "MAND", lat: 5.0556, lon: -75.4930 },
  { num: 0x5a0b0001, longName: "Albergue Chipre", shortName: "CHIP", lat: 5.0745, lon: -75.526 },
  { num: 0x5a0b0002, longName: "Ladera Aranjuez", shortName: "ARAN", lat: 5.059, lon: -75.4985 },
  { num: 0x5a0b0003, longName: "Brigada La Enea", shortName: "ENEA", lat: 5.0315, lon: -75.463 },
  { num: 0x5a0b0004, longName: "Puesto San José", shortName: "SJOS", lat: 5.07, lon: -75.5195 },
];
const CHATTER = [
  "Todos bien en el punto de encuentro",
  "Necesitamos agua potable para 30 personas",
  "Grieta grande en la vía, evacuando la cuadra",
  "Llegamos al albergue, 12 personas",
  "Recibido, quedamos atentos",
];

const now = () => Math.floor(Date.now() / 1000);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

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
    this.ev.node({ num: ME, longName: "Mi nodo (simulado)", shortName: "YO", battery: 87, lastHeard: now() });
    for (const n of NODES) {
      this.ev.node({ ...n, posTime: now(), battery: 40 + Math.floor(Math.random() * 60), lastHeard: now() });
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
      setTimeout(() => this.ev.text({ packetId: ++this.nextId, from: COMMAND, to: ME, ts: now(),
        text: "Recibido. Brigada en camino a su ubicación. Mantenga la calma." }), 4000);
    } else if (to !== BROADCAST) {
      setTimeout(() => this.ev.text({ packetId: ++this.nextId, from: to, to: ME, ts: now(),
        text: "Recibido 👍" }), 3500);
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
      this.ev.node({ num: n.num, lat: n.lat, lon: n.lon, posTime: now(), lastHeard: now() });
    } else {
      this.ev.text({ packetId: ++this.nextId, from: n.num, to: BROADCAST, ts: now(),
                     text: CHATTER[Math.floor(Math.random() * CHATTER.length)] });
    }
  }
}
