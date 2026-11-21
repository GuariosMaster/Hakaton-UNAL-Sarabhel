"""Servicio de Localización (GPS).

- red/albergue/+/pos  : guarda historial y última posición, revisa geocercas de
                        zonas de riesgo y emite events/position (+ events/alert al
                        entrar en una zona).
- red/albergue/+/info : nombre del nodo.
- red/albergue/+/tel  : energía (batería V, panel V, % de carga) y alerta de batería baja.
- red/gateway/+/estado: estado de cada gateway (tabla gateways) y alerta si se desconecta.
Cada trama registra en la tabla enlaces qué gateway escuchó al nodo y con qué señal.
"""
import threading
import time

from . import config, db, geo
from .bus import Bus

log = config.setup_logging("localizacion")


class LocationService:
    def __init__(self, bus: Bus):
        self.bus = bus
        self.conn = db.connect()
        self.lock = threading.Lock()
        self.zones = geo.load_zones(config.ZONES_FILE)
        threading.Thread(target=self._watchdog, daemon=True, name="gateways").start()

    # --- gateways ---------------------------------------------------------------
    GATEWAY_TIMEOUT_SECS = 150  # sin latido en 2,5 min (envían uno por minuto) = desconectado

    def on_gateway(self, _topic: str, p: dict) -> None:
        gid = p.get("gateway_id")
        if not gid:
            return
        with self.lock, self.conn:
            prev = self.conn.execute("SELECT estado FROM gateways WHERE gateway_id = ?", (gid,)).fetchone()
            row = db.upsert_gateway(self.conn, p)
        self.bus.publish(config.EV_GATEWAY, row)
        if row["estado"] == "desconectado" and prev and prev["estado"] == "conectado":
            self._gateway_down(row, "El gateway se desconectó del servidor (cable USB o equipo)")

    def _gateway_down(self, row: dict, motivo: str) -> None:
        log.warning("Gateway %s desconectado: %s", row["gateway_id"], motivo)
        with self.lock, self.conn:
            alert = db.create_alert(self.conn, {"type": "gateway_desconectado", "node_id": row["gateway_id"],
                                                "long_name": row.get("nombre") or row["gateway_id"], "text": motivo,
                                                "lat": row.get("lat"), "lon": row.get("lon"), "ts": db.now()})
        self.bus.publish(config.EV_ALERT, {**alert, "from_node": row["gateway_id"]})

    def _watchdog(self) -> None:
        """Marca como desconectado el gateway que dejó de enviar latidos (p. ej. se colgó el listener)."""
        while True:
            time.sleep(30)
            limite = db.now() - self.GATEWAY_TIMEOUT_SECS
            with self.lock:
                caidos = [dict(r) for r in self.conn.execute(
                    "SELECT * FROM gateways WHERE estado = 'conectado' AND last_seen < ?", (limite,))]
                with self.conn:
                    for g in caidos:
                        self.conn.execute("UPDATE gateways SET estado = 'desconectado' WHERE gateway_id = ?",
                                          (g["gateway_id"],))
            for g in caidos:
                g["estado"] = "desconectado"
                self.bus.publish(config.EV_GATEWAY, g)
                self._gateway_down(g, "El gateway dejó de responder")

    def _link(self, p: dict, node: str, ts: int) -> None:
        """Llamar dentro de self.lock + transacción."""
        if p.get("gateway"):
            db.touch_link(self.conn, node, p["gateway"], p.get("rssi"), ts)

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
            self._link(p, node, ts)
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
            with self.lock, self.conn:
                alert = db.create_alert(self.conn, {"type": "zona_riesgo", "node_id": node, "zone": zone,
                                                    "long_name": prev["long_name"], "lat": lat, "lon": lon,
                                                    "ts": ts})
            self.bus.publish(config.EV_ALERT, {**alert, "from_node": node})

    def on_nodeinfo(self, _topic: str, p: dict) -> None:
        node = p.get("from")
        if not node:
            return
        with self.lock, self.conn:
            db.touch_node(self.conn, node, int(p.get("ts") or db.now()))
            self._link(p, node, int(p.get("ts") or db.now()))
            self.conn.execute(
                "UPDATE nodes SET long_name = COALESCE(?, long_name), short_name = COALESCE(?, short_name) "
                "WHERE node_id = ?", (p.get("long_name"), p.get("short_name"), node))
        self._emit_node(node)

    def on_telemetry(self, _topic: str, p: dict) -> None:
        """Energía del nodo: voltaje de batería, voltaje del panel y % de carga."""
        node = p.get("from")
        if not node:
            return
        ts = int(p.get("ts") or db.now())
        battery = p.get("battery")
        with self.lock, self.conn:
            db.touch_node(self.conn, node, ts)
            self._link(p, node, ts)
            prev = self.conn.execute("SELECT battery, long_name, lat, lon FROM nodes WHERE node_id = ?",
                                     (node,)).fetchone()
            self.conn.execute(
                """UPDATE nodes SET battery = COALESCE(?, battery), voltage = COALESCE(?, voltage),
                                    panel_v = COALESCE(?, panel_v), rssi = COALESCE(?, rssi), energy_ts = ?
                   WHERE node_id = ?""",
                (battery, p.get("voltage"), p.get("panel_v"), p.get("rssi"), ts, node))
        self._emit_node(node)
        # Alerta solo al cruzar el umbral, no en cada trama.
        low = config.LOW_BATTERY_PCT
        if battery is not None and battery < low and (prev["battery"] is None or prev["battery"] >= low):
            log.warning("Batería baja en %s: %s%%", node, battery)
            with self.lock, self.conn:
                alert = db.create_alert(self.conn, {"type": "bateria_baja", "node_id": node, "battery": battery,
                                                    "long_name": prev["long_name"], "lat": prev["lat"],
                                                    "lon": prev["lon"], "ts": ts})
            self.bus.publish(config.EV_ALERT, {**alert, "from_node": node, "voltage": p.get("voltage")})

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
    bus.subscribe(config.GW_STATUS, svc.on_gateway)
    log.info("Servicio de localización iniciado (BD: %s)", config.DB_PATH)
    bus.run_forever()


if __name__ == "__main__":
    main()
