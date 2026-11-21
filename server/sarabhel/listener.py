"""Listener: puente entre el Gateway Meshtastic (serie/USB, TCP o simulado) y el broker.

Radio -> broker: traduce cada paquete a JSON y lo publica en lora/gateway/rx/<tipo>.
Broker -> radio: escucha lora/gateway/tx y lo transmite por LoRa.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any

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


# --- Conexión real con el radio ---------------------------------------------
class MeshLink:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.iface = None
        self.lost = threading.Event()

    def run(self) -> None:
        from pubsub import pub  # dependencia de la librería meshtastic

        pub.subscribe(self._on_receive, "meshtastic.receive")
        pub.subscribe(self._on_lost, "meshtastic.connection.lost")
        while True:
            try:
                self._open()
                for topic, payload in nodedb_to_events(self.iface.nodes):
                    self.bus.publish(topic, payload)
                self.lost.clear()
                self.lost.wait()
                log.warning("Conexión con el gateway perdida")
            except Exception as exc:
                log.error("No se pudo abrir el gateway (%s)", exc)
            self._close()
            time.sleep(5)

    def send(self, text: str, to: str | None) -> None:
        if self.iface is None:
            raise RuntimeError("gateway desconectado")
        self.iface.sendText(text, destinationId=to or "^all",
                            channelIndex=config.MESH_CHANNEL_INDEX)

    def _open(self) -> None:
        if config.MESH_CONNECTION == "serial":
            from meshtastic.serial_interface import SerialInterface
            log.info("Abriendo gateway por serie: %s", config.MESH_SERIAL_PORT or "autodetectar")
            self.iface = SerialInterface(devPath=config.MESH_SERIAL_PORT)
        elif config.MESH_CONNECTION == "tcp":
            from meshtastic.tcp_interface import TCPInterface
            if not config.MESH_TCP_HOST:
                raise RuntimeError("MESH_TCP_HOST no está definido")
            log.info("Abriendo gateway por TCP: %s", config.MESH_TCP_HOST)
            self.iface = TCPInterface(hostname=config.MESH_TCP_HOST)
        else:
            raise RuntimeError(f"MESH_CONNECTION desconocido: {config.MESH_CONNECTION}")
        log.info("Gateway conectado; %d nodos conocidos", len(self.iface.nodes or {}))

    def _close(self) -> None:
        if self.iface is not None:
            try:
                self.iface.close()
            except Exception:
                pass
            self.iface = None

    def _on_receive(self, packet, interface):  # firma exigida por pypubsub
        for topic, payload in packet_to_events(packet):
            log.debug("RX %s %s", topic, payload)
            self.bus.publish(topic, payload)

    def _on_lost(self, interface):
        self.lost.set()


def main() -> None:
    from .bus import Bus  # import diferido: permite importar el módulo sin paho en las pruebas

    bus = Bus("listener")
    if config.MESH_CONNECTION == "sim":
        from .simulator import Simulator
        link: Any = Simulator(bus)
    else:
        link = MeshLink(bus)

    # Los envíos se hacen en un hilo propio para no bloquear el hilo de red MQTT.
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
