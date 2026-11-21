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
    (3, "Albergue Chipre", 5.0800, -75.5260),
    (4, "Ladera Aranjuez", 5.0590, -75.4985),
    (5, "Brigada La Enea", 5.0315, -75.4630),
    (6, "Puesto San José", 5.0700, -75.5195),
]

# Gateways simulados y qué nodos escucha cada uno (Puesto San José lo oyen los dos:
# sirve para probar que el servidor descarta las tramas duplicadas).
GATEWAYS = [("gw-1", "Puesto de mando UNAL", 5.0556, -75.4930), ("gw-2", "Torre Chipre", 5.0760, -75.5230)]
OIDOS = {2: ("gw-1",), 3: ("gw-2",), 4: ("gw-1",), 5: ("gw-1",), 6: ("gw-1", "gw-2")}

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
        self.gateways = GATEWAYS[:config.SIM_GATEWAYS]
        self.gw_ids = {g[0] for g in self.gateways}
        self.last_beat = 0.0
        self.state = {
            n[0]: {"name": n[1], "lat": n[2], "lon": n[3], "carga": random.uniform(45, 95)} for n in NODES
        }

    def gateway_status(self) -> None:
        """Estado de los gateways simulados (como el latido de cada gateway USB real)."""
        self.last_beat = time.time()
        for gid, nombre, lat, lon in self.gateways:
            self.bus.publish(config.gw_topic(gid), {
                "gateway_id": gid, "nombre": nombre, "direccion": 1, "conexion": "sim", "estado": "conectado",
                "lat": lat, "lon": lon, "battery": 76, "voltage": 13.2, "panel_v": round(solar_factor(datetime.now()) * 18.4, 1),
                "ts": int(time.time())})

    def run(self) -> None:
        log.info("Simulando %d nodos FSK y %d gateway(s) cada %.1f s", len(NODES), len(self.gateways),
                 config.SIM_INTERVAL_SECS)
        self.gateway_status()
        for addr, st in self.state.items():
            self._emit({"nodo": addr, "tipo": "INFO", "nombre": st["name"]})
            self._emit({"nodo": addr, "tipo": "POS", **self._energy(addr), "lat": st["lat"], "lon": st["lon"]})
        while True:
            time.sleep(config.SIM_INTERVAL_SECS)
            if time.time() - self.last_beat > 60:
                self.gateway_status()
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
        # La misma trama la puede recibir más de un gateway, cada uno con su señal.
        oyentes = [g for g in OIDOS.get(frame["nodo"], ("gw-1",)) if g in self.gw_ids] or [self.gateways[0][0]]
        for gid in oyentes:
            frame["rssi"] = random.randint(-105, -60)
            for topic, payload in parse_line(json.dumps(frame, ensure_ascii=False), gid):
                self.bus.publish(topic, payload)

# --- Escenario de demo guionizado ------------------------------------------------
# Un sismo que siempre se desarrolla igual, para presentar el sistema (ver DEMO.md).
# (segundo, nodo, tipo, datos)
ESCENARIO = [
    (3, 2, "MSG", {"msg": "Sismo fuerte. Albergue Coliseo abierto"}),
    (12, 4, "MSG", {"msg": "Derrumbe en la ladera, via cerrada"}),
    (20, 4, "POS", {"lat": 5.0596, "lon": -75.4983}),  # entra a la zona de riesgo de ejemplo
    (30, 5, "MSG", {"msg": "SOS 3 personas atrapadas en vivienda colapsada en la calle 48, una herida"}),
    (42, 3, "MSG", {"msg": "Necesitamos agua para 120 personas"}),
    (55, 6, "TEL", {"carga": 18}),  # el kit de energía de San José se está agotando
    (68, 2, "MSG", {"msg": "Herido con fractura, necesito apoyo"}),
    (85, 5, "MSG", {"msg": "Rescatadas 2 personas, falta 1"}),
    (100, 3, "MSG", {"msg": "Llego agua, gracias"}),
    (115, 2, "MSG", {"msg": "Todos bien en punto de encuentro"}),
]


class Escenario(Simulator):
    """Reproduce ESCENARIO y después sigue con la simulación aleatoria."""

    def __init__(self, bus: Bus):
        super().__init__(bus)
        for addr, st in self.state.items():  # punto de partida conocido
            st["carga"] = {6: 24}.get(addr, 80)
        self.state[4]["lat"], self.state[4]["lon"] = 5.0655, -75.4985  # Aranjuez arranca fuera de la zona

    def run(self) -> None:
        log.info("Escenario de demo: %d eventos en %d s", len(ESCENARIO), ESCENARIO[-1][0])
        self.gateway_status()
        for addr, st in self.state.items():
            self._emit({"nodo": addr, "tipo": "INFO", "nombre": st["name"]})
            self._emit({"nodo": addr, "tipo": "POS", **self._energy(addr), "lat": st["lat"], "lon": st["lon"]})
        inicio = time.monotonic()
        for segundo, addr, tipo, datos in ESCENARIO:
            time.sleep(max(0.0, inicio + segundo - time.monotonic()))
            st = self.state[addr]
            if "carga" in datos:
                st["carga"] = datos["carga"]
            if tipo == "POS":
                st["lat"], st["lon"] = datos["lat"], datos["lon"]
            frame = {"nodo": addr, "tipo": tipo, **self._energy(addr)}
            if tipo == "POS":
                frame.update(lat=st["lat"], lon=st["lon"])
            elif tipo == "MSG":
                frame["msg"] = datos["msg"]
            log.info("[escenario %3ds] %s %s %s", segundo, st["name"], tipo, datos.get("msg", ""))
            self._emit(frame)
        log.info("Escenario terminado; continúa la simulación aleatoria")
        super().run()
