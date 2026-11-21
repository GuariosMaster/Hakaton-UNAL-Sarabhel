"""Servicio de Localización (GPS).

- lora/gateway/rx/position  : guarda historial y última posición, revisa geocercas de
                      zonas de riesgo y emite events/position (+ events/alert al
                      entrar en una zona).
- lora/gateway/rx/nodeinfo  : nombre del nodo.
- lora/gateway/rx/telemetry : batería / voltaje.
"""
import threading

from . import config, db, geo
from .bus import Bus

log = config.setup_logging("localizacion")


class LocationService:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.conn = db.connect()
        self.lock = threading.Lock()
        self.zones = geo.load_zones(config.ZONES_FILE)

    def on_position(self, _topic: str, p: dict) -> None:
        node, lat, lon = p.get("from"), p.get("lat"), p.get("lon")
        if not node or not geo.valid_coords(lat, lon):
            log.debug("Posición inválida descartada: %r", p)
            return
        lat, lon = float(lat), float(lon)
        ts = int(p.get("ts") or db.now())
        zone = geo.find_zone(self.zones, lat, lon)
        with self.lock, self.conn:
            db.touch_node(self.conn, node, ts)
            prev = self.conn.execute("SELECT risk_zone, long_name, pos_ts FROM nodes WHERE node_id = ?",
                                     (node,)).fetchone()
            self.conn.execute("INSERT INTO positions (node_id, lat, lon, alt, ts) VALUES (?, ?, ?, ?, ?)",
                              (node, lat, lon, p.get("alt"), ts))
            # No retroceder la "última posición" si llega un paquete viejo (reintentos de la malla).
            if prev["pos_ts"] is None or ts >= prev["pos_ts"]:
                self.conn.execute(
                    "UPDATE nodes SET lat = ?, lon = ?, alt = ?, pos_ts = ?, risk_zone = ? WHERE node_id = ?",
                    (lat, lon, p.get("alt"), ts, zone, node),
                )
            else:
                zone = prev["risk_zone"]
        self.bus.publish(config.EV_POSITION, {"node_id": node, "lat": lat, "lon": lon, "alt": p.get("alt"),
                                              "ts": ts, "risk_zone": zone})
        if zone and zone != prev["risk_zone"]:
            log.warning("Nodo %s entró en zona de riesgo: %s", node, zone)
            self.bus.publish(config.EV_ALERT, {"type": "zona_riesgo", "from_node": node,
                                               "long_name": prev["long_name"], "zone": zone,
                                               "lat": lat, "lon": lon, "ts": ts})

    def on_nodeinfo(self, _topic: str, p: dict) -> None:
        node = p.get("from")
        if not node:
            return
        with self.lock, self.conn:
            db.touch_node(self.conn, node, int(p.get("ts") or db.now()))
            self.conn.execute(
                "UPDATE nodes SET long_name = COALESCE(?, long_name), short_name = COALESCE(?, short_name) "
                "WHERE node_id = ?", (p.get("long_name"), p.get("short_name"), node))
        self._emit_node(node)

    def on_telemetry(self, _topic: str, p: dict) -> None:
        node = p.get("from")
        if not node:
            return
        with self.lock, self.conn:
            db.touch_node(self.conn, node, int(p.get("ts") or db.now()))
            self.conn.execute(
                "UPDATE nodes SET battery = COALESCE(?, battery), voltage = COALESCE(?, voltage) "
                "WHERE node_id = ?", (p.get("battery"), p.get("voltage"), node))
        self._emit_node(node)

    def _emit_node(self, node: str) -> None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node,)).fetchone()
        if row:
            self.bus.publish(config.EV_NODE, dict(row))


def main() -> None:
    bus = Bus("localizacion")
    svc = LocationService(bus)
    bus.subscribe(config.RX_POSITION, svc.on_position)
    bus.subscribe(config.RX_NODEINFO, svc.on_nodeinfo)
    bus.subscribe(config.RX_TELEMETRY, svc.on_telemetry)
    log.info("Servicio de localización iniciado (BD: %s)", config.DB_PATH)
    bus.run_forever()


if __name__ == "__main__":
    main()
