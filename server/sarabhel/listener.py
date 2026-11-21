"""Listener: puente entre el gateway ESP32-S3 + RFM69HCW (USB serie) y el broker MQTT.

<<<<<<< HEAD
Radio -> broker: cada línea JSON del gateway se publica en red/albergue/{nodo}/{msg|tel|pos|info}.
Broker -> radio: lo que llega a red/tx/msg se escribe en el gateway para transmitirlo.
Con MESH_CONNECTION=sim se simulan nodos de albergue; con escenario, un sismo guionizado (DEMO.md).
=======
Radio -> broker: traduce cada paquete a JSON y lo publica en lora/gateway/rx/<tipo>.
Broker -> radio: escucha lora/gateway/tx y lo transmite por LoRa.
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any

<<<<<<< HEAD
from . import config, db
from .bus import Bus
from .gateway import encode_tx, parse_line

log = config.setup_logging("listener")

# Chips USB habituales: Espressif nativo (ESP32-S3/C6), Silicon Labs CP210x, WCH CH340.
_KNOWN_VIDS = {0x303A: "Espressif", 0x10C4: "CP210x", 0x1A86: "CH340"}
HEARTBEAT_SECS = 60


def find_ports() -> list[str]:
    from serial.tools import list_ports

    ports = list(list_ports.comports())
    found = [p.device for p in ports if p.vid in _KNOWN_VIDS]
    if not found:
        names = ", ".join(p.device for p in ports) or "ninguno"
        raise RuntimeError(f"No se encontró ningún gateway ESP32. Puertos disponibles: {names}. "
                           "Indica los puertos con MESH_USB_DEVICE (separados por coma).")
    return found
=======
from . import config

log = config.setup_logging("listener")


# --- Traducción de paquetes Meshtastic a eventos JSON -----------------------
def packet_to_events(packet: dict[str, Any]) -> list[tuple[str, dict]]:
    """Convierte un paquete decodificado de la librería meshtastic en (tema, payload)."""
    decoded = packet.get("decoded") or {}
    portnum = decoded.get("portnum")
    node = packet.get("fromId")
    if not node or not portnum:
        return []  # paquete cifrado para otro canal o sin remitente
    ts = int(packet.get("rxTime") or time.time())
    radio = {"rssi": packet.get("rxRssi"), "snr": packet.get("rxSnr")}

    if portnum == "TEXT_MESSAGE_APP" and decoded.get("text"):
        return [(config.RX_TEXT, {
            "packet_id": packet.get("id"),
            "from": node,
            "to": packet.get("toId"),
            "channel": packet.get("channel", 0),
            "text": decoded["text"],
            "ts": ts,
            **radio,
        })]

    if portnum == "POSITION_APP":
        pos = decoded.get("position") or {}
        lat, lon = pos.get("latitude"), pos.get("longitude")
        if lat is None or lon is None:
            return []
        return [(config.RX_POSITION, {
            "packet_id": packet.get("id"),
            "from": node,
            "lat": lat,
            "lon": lon,
            "alt": pos.get("altitude"),
            "sats": pos.get("satsInView"),
            "ts": int(pos.get("time") or ts),
            **radio,
        })]

    if portnum == "NODEINFO_APP":
        user = decoded.get("user") or {}
        return [(config.RX_NODEINFO, {
            "packet_id": packet.get("id"),
            "from": node,
            "long_name": user.get("longName"),
            "short_name": user.get("shortName"),
            "ts": ts,
        })]

    if portnum == "TELEMETRY_APP":
        metrics = (decoded.get("telemetry") or {}).get("deviceMetrics")
        if not metrics:
            return []
        return [(config.RX_TELEMETRY, {
            "packet_id": packet.get("id"),
            "from": node,
            "battery": metrics.get("batteryLevel"),
            "voltage": metrics.get("voltage"),
            "ts": ts,
        })]

    return []


def nodedb_to_events(nodes: dict[str, dict]) -> list[tuple[str, dict]]:
    """Vuelca la tabla de nodos que el gateway ya conoce al conectarse."""
    events = []
    for node_id, info in (nodes or {}).items():
        user = info.get("user") or {}
        ts = int(info.get("lastHeard") or time.time())
        events.append((config.RX_NODEINFO, {
            "from": node_id, "long_name": user.get("longName"),
            "short_name": user.get("shortName"), "ts": ts,
        }))
        pos = info.get("position") or {}
        if pos.get("latitude") is not None and pos.get("longitude") is not None:
            events.append((config.RX_POSITION, {
                "from": node_id, "lat": pos["latitude"], "lon": pos["longitude"],
                "alt": pos.get("altitude"), "ts": int(pos.get("time") or ts),
            }))
        # La tabla de nodos del gateway ya trae batería/voltaje: publicarlos al
        # arrancar evita que el dashboard muestre nodos reales sin telemetría
        # hasta que llegue el siguiente broadcast (puede tardar 15 min).
        metrics = info.get("deviceMetrics") or {}
        if metrics.get("batteryLevel") is not None or metrics.get("voltage") is not None:
            events.append((config.RX_TELEMETRY, {
                "from": node_id,
                "battery": metrics.get("batteryLevel"),
                "voltage": metrics.get("voltage"),
                "ts": ts,
            }))
    return events
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9


class UsbGateway:
    """Un gateway conectado por USB. Publica sus tramas y su estado (conectado/desconectado)."""

    def __init__(self, bus: Bus, gateway_id: str, device: str | None, nombre: str | None):
        self.bus = bus
        self.gateway_id = gateway_id
        self.device = device
        self.nombre = nombre
        self.port: Any = None
        self.lock = threading.Lock()
        self.connected = False

    def status(self, estado: str) -> None:
        self.connected = estado == "conectado"
        self.bus.publish(config.gw_topic(self.gateway_id), {
            "gateway_id": self.gateway_id, "estado": estado, "nombre": self.nombre,
            "conexion": f"usb:{self.device or 'auto'}", "ts": int(time.time())})

    def run(self) -> None:
        import serial

        while True:
            try:
                device = self.device or find_ports()[0]
                self.device = device
                log.info("[%s] abriendo gateway en %s a %d baudios", self.gateway_id, device, config.MESH_USB_BAUD)
                with serial.Serial(device, config.MESH_USB_BAUD, timeout=1) as port:
                    self.port = port
                    self.status("conectado")
                    log.info("[%s] gateway conectado", self.gateway_id)
                    last_beat = time.time()
                    while True:
                        raw = port.readline()
                        if time.time() - last_beat > HEARTBEAT_SECS:
                            self.status("conectado")  # latido: el servidor sabe que sigue vivo
                            last_beat = time.time()
                        if not raw:
                            continue
                        line = raw.decode("utf-8", errors="replace")
                        events = parse_line(line, self.gateway_id)
                        if not events and line.strip():
                            log.debug("[%s] %s", self.gateway_id, line.strip())
                        for topic, payload in events:
                            if payload.get("gateway_id") == self.gateway_id and self.nombre:
                                payload["nombre"] = payload.get("nombre") or self.nombre
                            self.bus.publish(topic, payload)
            except Exception as exc:
                log.error("[%s] gateway no disponible (%s); reintento en 5 s", self.gateway_id, exc)
            self.port = None
            if self.connected:
                self.status("desconectado")
            time.sleep(5)

    def send(self, text: str, to: str | None) -> None:
        line = encode_tx(text, to)
        if line is None:
            return
        if self.port is None:
            raise RuntimeError(f"gateway {self.gateway_id} desconectado")
        with self.lock:
            self.port.write(line.encode("utf-8"))
            self.port.flush()


class GatewayPool:
    """Varios gateways: recibe de todos y envía cada mensaje por el que mejor escucha al destino."""

    def __init__(self, gateways: list):
        self.gateways = {g.gateway_id: g for g in gateways}

    def run(self) -> None:
        threads = [threading.Thread(target=g.run, daemon=True, name=gid) for gid, g in self.gateways.items()]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def send(self, text: str, to: str | None) -> None:
        online = [g for g in self.gateways.values() if g.connected]
        if not online:
            raise RuntimeError("ningún gateway conectado")
        if to in (None, "", "^all"):
            for g in online:  # a todos: por cada gateway (cada uno lo reparte a los nodos que conoce)
                g.send(text, to)
            return
        conn = db.connect()
        try:
            best = db.best_gateway(conn, to)
        finally:
            conn.close()
        target = self.gateways.get(best) if best else None
        if target is None or not target.connected:
            target = online[0]
            log.warning("Sin enlace reciente con %s; se envía por %s", to, target.gateway_id)
        target.send(text, to)


def build_usb_pool(bus: Bus) -> GatewayPool:
    devices = [d.strip() for d in (config.MESH_USB_DEVICE or "").split(",") if d.strip()]
    if not devices:
        try:
            devices = find_ports()
        except RuntimeError as exc:
            log.error("%s", exc)
            devices = [None]  # reintenta autodetectar en el hilo del gateway
    gws = []
    for i, dev in enumerate(devices):
        nombre = config.MESH_GATEWAY_NAMES[i] if i < len(config.MESH_GATEWAY_NAMES) else None
        gws.append(UsbGateway(bus, f"gw-{i + 1}", dev, nombre))
    log.info("Gateways USB: %s", ", ".join(f"{g.gateway_id}={g.device or 'auto'}" for g in gws))
    return GatewayPool(gws)


def main() -> None:
    from .bus import Bus  # import diferido: permite importar el módulo sin paho en las pruebas

    bus = Bus("listener")
    if config.MESH_CONNECTION == "sim":
        from .simulator import Simulator
        link: Any = Simulator(bus)
    elif config.MESH_CONNECTION == "escenario":
        from .simulator import Escenario
        link = Escenario(bus)
    elif config.MESH_CONNECTION == "usb":
        link = build_usb_pool(bus)
    else:
        raise SystemExit(f"MESH_CONNECTION desconocido: {config.MESH_CONNECTION} (usa sim, escenario o usb)")

    # Los envíos van en un hilo propio para no bloquear el hilo de red MQTT.
    outbox: queue.Queue = queue.Queue(maxsize=100)

    def on_tx(_topic: str, payload: dict) -> None:
        try:
            outbox.put_nowait(payload)
        except queue.Full:
            log.error("Cola de salida llena; mensaje descartado: %r", payload)

    def sender() -> None:
        while True:
            payload = outbox.get()
            try:
                link.send(payload["text"], payload.get("to"))
                log.info("TX -> %s: %s", payload.get("to") or "todos", payload["text"])
            except Exception as exc:
                log.error("Fallo al transmitir (%s); reintento en 5 s", exc)
                time.sleep(5)
                try:
                    outbox.put_nowait(payload)
                except queue.Full:
                    pass

    bus.subscribe(config.TX_TEXT, on_tx)
    bus.start()
    threading.Thread(target=sender, daemon=True, name="sender").start()
    log.info("Listener iniciado en modo %s", config.MESH_CONNECTION)
    link.run()


if __name__ == "__main__":
    main()
