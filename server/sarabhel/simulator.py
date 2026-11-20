"""Simulador de nodos de campo para demos y pruebas sin hardware.

Genera los mismos paquetes que produciría la librería meshtastic y los pasa por
packet_to_events, así el resto del sistema no distingue simulación de radio real.
Coordenadas aproximadas alrededor de Manizales; los datos son ficticios.
"""
import logging
import random
import time

from . import config
from .bus import Bus

log = logging.getLogger("listener.sim")

NODES = [
    # id, nombre largo, corto, lat, lon
    ("!5a0b0001", "Albergue Chipre", "CHIP", 5.0745, -75.5260),
    ("!5a0b0002", "Ladera Aranjuez", "ARAN", 5.0590, -75.4985),
    ("!5a0b0003", "Brigada La Enea", "ENEA", 5.0315, -75.4630),
    ("!5a0b0004", "Puesto San José", "SJOS", 5.0700, -75.5195),
    ("!5a0b0005", "Rescate Palermo", "PALE", 5.0560, -75.4870),
]

MESSAGES = [
    "SOS hay personas atrapadas bajo escombros",
    "Tenemos un herido con fractura en la pierna",
    "Necesitamos agua potable para 30 personas",
    "Se acabaron los medicamentos en el albergue",
    "Grieta grande en la vía, evacuando la cuadra",
    "Todos bien en el punto de encuentro",
    "Llegamos al albergue, 12 personas",
    "Derrumbe en la ladera, la carretera está bloqueada",
    "Olor a gas en la calle principal",
    "Necesitamos cobijas, hace mucho frío",
    "Recibido, quedamos atentos",
]


class Simulator:
    def __init__(self, bus: Bus):
        from .listener import packet_to_events  # import diferido: evita ciclo

        self._to_events = packet_to_events
        self.bus = bus
        self.state = {n[0]: {"lat": n[3], "lon": n[4], "battery": random.randint(55, 100)} for n in NODES}
        self.names = {n[0]: (n[1], n[2]) for n in NODES}
        self._pid = random.randint(1, 10_000)

    def run(self) -> None:
        log.info("Simulando %d nodos cada %.1f s", len(NODES), config.SIM_INTERVAL_SECS)
        for node_id in self.state:
            self._emit(node_id, "NODEINFO_APP")
            self._emit(node_id, "POSITION_APP")
            self._emit(node_id, "TELEMETRY_APP")
        while True:
            time.sleep(config.SIM_INTERVAL_SECS)
            node_id = random.choice(list(self.state))
            roll = random.random()
            if roll < 0.55:
                st = self.state[node_id]
                st["lat"] += random.uniform(-0.0012, 0.0012)
                st["lon"] += random.uniform(-0.0012, 0.0012)
                self._emit(node_id, "POSITION_APP")
            elif roll < 0.85:
                self._emit(node_id, "TEXT_MESSAGE_APP", text=random.choice(MESSAGES))
            else:
                st = self.state[node_id]
                st["battery"] = max(5, st["battery"] - random.randint(0, 3))
                self._emit(node_id, "TELEMETRY_APP")

    def send(self, text: str, to: str | None) -> None:
        log.info("[sim] transmitido por radio a %s: %s", to or "todos", text)

    def _emit(self, node_id: str, portnum: str, text: str | None = None) -> None:
        st = self.state[node_id]
        long_name, short_name = self.names[node_id]
        decoded: dict = {"portnum": portnum}
        if portnum == "TEXT_MESSAGE_APP":
            decoded["text"] = text
        elif portnum == "POSITION_APP":
            decoded["position"] = {"latitude": round(st["lat"], 6), "longitude": round(st["lon"], 6),
                                   "altitude": random.randint(1900, 2300), "satsInView": random.randint(5, 12),
                                   "time": int(time.time())}
        elif portnum == "NODEINFO_APP":
            decoded["user"] = {"id": node_id, "longName": long_name, "shortName": short_name}
        elif portnum == "TELEMETRY_APP":
            decoded["telemetry"] = {"deviceMetrics": {"batteryLevel": st["battery"],
                                                      "voltage": round(3.3 + st["battery"] / 100 * 0.9, 2)}}
        self._pid += 1
        packet = {"id": self._pid, "fromId": node_id, "toId": "^all", "channel": 0,
                  "rxTime": int(time.time()), "rxRssi": random.randint(-120, -70),
                  "rxSnr": round(random.uniform(-12, 10), 1), "decoded": decoded}
        for topic, payload in self._to_events(packet):
            self.bus.publish(topic, payload)
