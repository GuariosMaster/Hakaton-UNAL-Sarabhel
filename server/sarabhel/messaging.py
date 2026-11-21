"""Servicio de Mensajería.

- red/albergue/+/msg : clasifica prioridad, adjunta la última posición conocida del
                 remitente, guarda en SQLite y emite events/msg (y events/alert
                 si es crítico).
- app/send     : valida un mensaje del puesto de mando, lo guarda y lo entrega
                 al listener (red/tx/msg) para transmitirlo por radio FSK.
"""
import re
import threading

from . import config, db, geo
from .bus import Bus
from .priority import CRITICO, classify

log = config.setup_logging("mensajeria")

# La app móvil agrega la ubicación del teléfono al final: "SOS Herido 📍5.07012,-75.51234"
_COORDS = re.compile(r"📍\s*(-?\d{1,2}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*$")


def coords_in_text(text: str) -> tuple[float, float] | None:
    m = _COORDS.search(text)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    return (lat, lon) if geo.valid_coords(lat, lon) else None


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
        gateway = p.get("gateway")
        with self.lock, self.conn:
            db.touch_node(self.conn, node, ts)
            if gateway:
                db.touch_link(self.conn, node, gateway, p.get("rssi"), ts)
            # Varios gateways pueden recibir la misma trama: si ya entró hace unos segundos, se descarta.
            dup = self.conn.execute(
                """SELECT id FROM messages WHERE direction = 'in' AND from_node = ? AND text = ? AND ts >= ?
                   LIMIT 1""", (node, text, ts - db.DUPLICATE_WINDOW_SECS)).fetchone()
            if dup:
                log.info("Duplicado de %s (también por %s), descartado", node, gateway or "?")
                return
            row = self.conn.execute("SELECT lat, lon, long_name FROM nodes WHERE node_id = ?", (node,)).fetchone()
            # Prioridad: ubicación enviada con el mensaje > coordenadas en el texto > última posición del nodo.
            sent = (p["lat"], p["lon"]) if geo.valid_coords(p.get("lat"), p.get("lon")) else None
            lat, lon = sent or coords_in_text(text) or ((row["lat"], row["lon"]) if row else (None, None))
            if priority == CRITICO:
                self.conn.execute("UPDATE nodes SET alert_ts = ? WHERE node_id = ?", (ts, node))
            cur = self.conn.execute(
                """INSERT INTO messages (packet_id, direction, from_node, to_node, channel, text,
                                         priority, lat, lon, rssi, snr, ts, gateway_id)
                   VALUES (?, 'in', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (p.get("packet_id"), node, p.get("to"), p.get("channel"), text, priority,
                 lat, lon, p.get("rssi"), p.get("snr"), ts, gateway),
            )
            alert = None
            if priority == CRITICO:
                alert = db.create_alert(self.conn, {"type": "mensaje_critico", "node_id": node, "text": text,
                                                    "long_name": row["long_name"] if row else None,
                                                    "lat": lat, "lon": lon, "ts": ts})
        event = {"id": cur.lastrowid, "direction": "in", "from_node": node, "to_node": p.get("to"),
                 "long_name": row["long_name"] if row else None, "text": text, "priority": priority,
                 "lat": lat, "lon": lon, "rssi": p.get("rssi"), "snr": p.get("snr"), "ts": ts,
                 "gateway_id": gateway}
        self.bus.publish(config.EV_MESSAGE, event)
        if alert:
            self.bus.publish(config.EV_ALERT, {**alert, "from_node": node})
            log.warning("ALERTA CRÍTICA de %s: %s", node, text)
        else:
            log.info("Mensaje %s de %s: %s", priority, node, text)

    def on_send(self, _topic: str, p: dict) -> None:
        text = str(p.get("text", "")).strip()
        to = p.get("to") or None
        if not text:
            return
        if len(text.encode("utf-8")) > config.MAX_TEXT_BYTES:
            log.error("Mensaje demasiado largo para la radio FSK, descartado")
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
