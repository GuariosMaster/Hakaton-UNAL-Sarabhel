"""Servicio de Mensajería.

- mesh/rx/text : clasifica prioridad, adjunta la última posición conocida del
                 remitente, guarda en SQLite y emite events/msg (y events/alert
                 si es crítico).
- app/send     : valida un mensaje del puesto de mando, lo guarda y lo entrega
                 al listener (mesh/tx/text) para transmitirlo por radio.
"""
import threading

from . import config, db
from .bus import Bus
from .priority import CRITICO, classify

log = config.setup_logging("mensajeria")


class MessagingService:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.conn = db.connect()
        self.lock = threading.Lock()

    def on_text(self, _topic: str, p: dict) -> None:
        text = str(p.get("text", "")).strip()
        node = p.get("from")
        if not text or not node:
            return
        ts = int(p.get("ts") or db.now())
        priority = classify(text)
        with self.lock, self.conn:
            db.touch_node(self.conn, node, ts)
            row = self.conn.execute("SELECT lat, lon, long_name FROM nodes WHERE node_id = ?", (node,)).fetchone()
            lat, lon = (row["lat"], row["lon"]) if row else (None, None)
            if priority == CRITICO:
                self.conn.execute("UPDATE nodes SET alert_ts = ? WHERE node_id = ?", (ts, node))
            cur = self.conn.execute(
                """INSERT INTO messages (packet_id, direction, from_node, to_node, channel, text,
                                         priority, lat, lon, rssi, snr, ts)
                   VALUES (?, 'in', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p.get("packet_id"), node, p.get("to"), p.get("channel"), text, priority,
                 lat, lon, p.get("rssi"), p.get("snr"), ts),
            )
        event = {"id": cur.lastrowid, "direction": "in", "from_node": node, "to_node": p.get("to"),
                 "long_name": row["long_name"] if row else None, "text": text, "priority": priority,
                 "lat": lat, "lon": lon, "rssi": p.get("rssi"), "snr": p.get("snr"), "ts": ts}
        self.bus.publish(config.EV_MESSAGE, event)
        if priority == CRITICO:
            self.bus.publish(config.EV_ALERT, {"type": "mensaje_critico", **event})
            log.warning("ALERTA CRÍTICA de %s: %s", node, text)
        else:
            log.info("Mensaje %s de %s: %s", priority, node, text)

    def on_send(self, _topic: str, p: dict) -> None:
        text = str(p.get("text", "")).strip()
        to = p.get("to") or None
        if not text:
            return
        if len(text.encode("utf-8")) > config.MAX_TEXT_BYTES:
            log.error("Mensaje demasiado largo para LoRa, descartado")
            return
        ts = db.now()
        with self.lock, self.conn:
            cur = self.conn.execute(
                """INSERT INTO messages (direction, from_node, to_node, text, priority, ts)
                   VALUES ('out', 'puesto-mando', ?, ?, ?, ?)""",
                (to, text, classify(text), ts),
            )
        self.bus.publish(config.TX_TEXT, {"text": text, "to": to, "message_id": cur.lastrowid})
        self.bus.publish(config.EV_MESSAGE, {"id": cur.lastrowid, "direction": "out",
                                             "from_node": "puesto-mando", "to_node": to, "text": text,
                                             "priority": classify(text), "ts": ts})


def main() -> None:
    bus = Bus("mensajeria")
    svc = MessagingService(bus)
    bus.subscribe(config.RX_TEXT, svc.on_text)
    bus.subscribe(config.APP_SEND, svc.on_send)
    log.info("Servicio de mensajería iniciado (BD: %s)", config.DB_PATH)
    bus.run_forever()


if __name__ == "__main__":
    main()
