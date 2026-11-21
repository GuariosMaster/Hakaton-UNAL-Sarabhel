"""Listener: puente entre el gateway ESP32-S3 + RFM69HCW (USB serie) y el broker MQTT.

Radio -> broker: cada línea JSON del gateway se publica en red/albergue/{nodo}/{msg|tel|pos|info}.
Broker -> radio: lo que llega a red/tx/msg se escribe en el gateway para transmitirlo.
Con MESH_CONNECTION=sim se simulan nodos de albergue (demo sin hardware).
"""
import queue
import threading
import time
from typing import Any

from . import config
from .bus import Bus
from .gateway import encode_tx, parse_line

log = config.setup_logging("listener")

# Chips USB habituales: Espressif nativo (ESP32-S3/C6), Silicon Labs CP210x, WCH CH340.
_KNOWN_VIDS = {0x303A: "Espressif", 0x10C4: "CP210x", 0x1A86: "CH340"}


def find_port() -> str:
    from serial.tools import list_ports

    ports = list(list_ports.comports())
    for p in ports:
        if p.vid in _KNOWN_VIDS:
            log.info("Gateway detectado en %s (%s)", p.device, _KNOWN_VIDS[p.vid])
            return p.device
    names = ", ".join(p.device for p in ports) or "ninguno"
    raise RuntimeError(f"No se encontró el gateway ESP32. Puertos disponibles: {names}. "
                       "Indica el puerto con MESH_USB_DEVICE.")


class UsbGateway:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.port: Any = None
        self.lock = threading.Lock()

    def run(self) -> None:
        import serial

        while True:
            try:
                device = config.MESH_USB_DEVICE or find_port()
                log.info("Abriendo gateway en %s a %d baudios", device, config.MESH_USB_BAUD)
                with serial.Serial(device, config.MESH_USB_BAUD, timeout=1) as port:
                    self.port = port
                    log.info("Gateway conectado")
                    while True:
                        raw = port.readline()
                        if not raw:
                            continue
                        line = raw.decode("utf-8", errors="replace")
                        events = parse_line(line)
                        if not events and line.strip():
                            log.debug("Gateway: %s", line.strip())
                        for topic, payload in events:
                            self.bus.publish(topic, payload)
            except Exception as exc:
                log.error("Gateway no disponible (%s); reintento en 5 s", exc)
            self.port = None
            time.sleep(5)

    def send(self, text: str, to: str | None) -> None:
        line = encode_tx(text, to)
        if line is None:
            return
        if self.port is None:
            raise RuntimeError("gateway desconectado")
        with self.lock:
            self.port.write(line.encode("utf-8"))
            self.port.flush()


def main() -> None:
    bus = Bus("listener")
    if config.MESH_CONNECTION == "sim":
        from .simulator import Simulator
        link: Any = Simulator(bus)
    elif config.MESH_CONNECTION == "usb":
        link = UsbGateway(bus)
    else:
        raise SystemExit(f"MESH_CONNECTION desconocido: {config.MESH_CONNECTION} (usa sim o usb)")

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
