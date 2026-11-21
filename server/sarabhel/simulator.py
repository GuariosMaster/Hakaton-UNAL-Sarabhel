"""Simulador de nodos de albergue FSK 915 MHz para demos y pruebas sin hardware.

Genera las mismas líneas JSON que enviaría el gateway ESP32-S3 por USB y las pasa
por gateway.parse_line, así el resto del sistema no distingue simulación de radio real.
La energía sigue el ciclo solar: el panel produce de día y la batería se descarga de noche.
Coordenadas aproximadas en Manizales; los datos son ficticios.
"""
import json
import logging
import math
import random
import time
from datetime import datetime

from . import config
from .bus import Bus
from .gateway import parse_line

log = logging.getLogger("listener.sim")

NODES = [
    # dirección RHMesh, nombre, lat, lon
    (2, "Albergue Coliseo", 5.0640, -75.4990),
    (3, "Albergue Chipre", 5.0745, -75.5260),
    (4, "Ladera Aranjuez", 5.0590, -75.4985),
    (5, "Brigada La Enea", 5.0315, -75.4630),
    (6, "Puesto San José", 5.0700, -75.5195),
]

MESSAGES = [
    "SOS personas atrapadas en escombros",
    "Herido con fractura, necesito apoyo",
    "Necesitamos agua para 30 personas",
    "Sin medicamentos en el albergue",
    "Grieta en la via, evacuando",
    "Todos bien en punto de encuentro",
    "280 personas en albergue, sin red",
    "Derrumbe en la ladera, via cerrada",
    "Olor a gas en la calle principal",
    "Necesitamos cobijas, mucho frio",
    "Recibido, quedamos atentos",
]


def solar_factor(now: datetime) -> float:
    """0 de noche, 1 al mediodía (aproximación senoidal entre 6:00 y 18:00)."""
    h = now.hour + now.minute / 60
    return max(0.0, math.sin(math.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0.0


class Simulator:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.state = {
            n[0]: {"name": n[1], "lat": n[2], "lon": n[3], "carga": random.uniform(45, 95)} for n in NODES
        }

    def run(self) -> None:
        log.info("Simulando %d nodos FSK cada %.1f s", len(NODES), config.SIM_INTERVAL_SECS)
        for addr, st in self.state.items():
            self._emit({"nodo": addr, "tipo": "INFO", "nombre": st["name"]})
            self._emit({"nodo": addr, "tipo": "POS", **self._energy(addr), "lat": st["lat"], "lon": st["lon"]})
        while True:
            time.sleep(config.SIM_INTERVAL_SECS)
            addr = random.choice(list(self.state))
            st = self.state[addr]
            roll = random.random()
            if roll < 0.35:
                st["lat"] += random.uniform(-0.0008, 0.0008)
                st["lon"] += random.uniform(-0.0008, 0.0008)
                self._emit({"nodo": addr, "tipo": "POS", **self._energy(addr),
                            "lat": round(st["lat"], 6), "lon": round(st["lon"], 6)})
            elif roll < 0.65:
                self._emit({"nodo": addr, "tipo": "MSG", **self._energy(addr), "msg": random.choice(MESSAGES)})
            else:
                self._emit({"nodo": addr, "tipo": "TEL", **self._energy(addr)})

    def send(self, text: str, to: str | None) -> None:
        log.info("[sim] transmitido por radio FSK a %s: %s", to or "todos", text)

    def _energy(self, addr: int) -> dict:
        st = self.state[addr]
        sun = solar_factor(datetime.now())
        # De día el panel carga la batería; de noche el nodo la descarga.
        # Ritmo comprimido para la demo: unas décimas de % por trama (no horas reales).
        st["carga"] = min(100.0, max(3.0, st["carga"] + (sun * 0.25 - 0.06) * random.uniform(0.5, 1.5)))
        panel = round(sun * random.uniform(17.0, 19.5), 1)
        bat = round(12.0 + st["carga"] / 100 * 1.6, 2)  # LiFePO4 4S: ~12,0 V vacía, ~13,6 V llena
        return {"bat": bat, "panel": panel, "carga": int(st["carga"])}

    def _emit(self, frame: dict) -> None:
        frame["rssi"] = random.randint(-105, -60)
        for topic, payload in parse_line(json.dumps(frame, ensure_ascii=False)):
            self.bus.publish(topic, payload)
