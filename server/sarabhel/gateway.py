"""Protocolo entre el gateway ESP32-S3 + RFM69HCW y el servidor (USB serie, 115.200 baudios).

Gateway -> servidor: una línea JSON por trama recibida por radio, por ejemplo
    {"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,"msg":"Albergue Coliseo: 280 personas","rssi":-72}
    {"nodo":2,"tipo":"TEL","bat":12.4,"panel":18.1,"carga":82,"rssi":-70}
    {"nodo":2,"tipo":"POS","bat":12.4,"panel":18.1,"carga":82,"lat":5.0689,"lon":-75.5174,"rssi":-71}
    {"nodo":2,"tipo":"INFO","nombre":"Albergue Coliseo","rssi":-70}
Las líneas que no son JSON (mensajes de depuración del firmware) se ignoran.

Servidor -> gateway: una línea JSON por mensaje a transmitir
    {"dest":2,"msg":"Brigada en camino"}      (dest 255 = todos los nodos conocidos)
"""
import json
import time
from typing import Any

from . import config


def _num(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def parse_line(line: str) -> list[tuple[str, dict]]:
    """Convierte una línea del gateway en eventos (tema MQTT, payload)."""
    line = line.strip()
    if not line.startswith("{"):
        return []
    try:
        d = json.loads(line)
        address = int(d["nodo"])
    except (ValueError, KeyError, TypeError):
        return []
    if not 1 <= address <= 254:
        return []

    node = config.node_id(address)
    tipo = str(d.get("tipo", "MSG")).upper()
    ts = int(time.time())
    rssi = _num(d.get("rssi"))
    events: list[tuple[str, dict]] = []

    # Cada trama del nodo trae su estado de energía (TIPO|BAT_V|PANEL_V|CARGA_PCT|...).
    bat, panel, carga = _num(d.get("bat")), _num(d.get("panel")), _num(d.get("carga"))
    if any(v is not None for v in (bat, panel, carga)):
        events.append((config.rx_topic("tel", node), {
            "from": node, "voltage": bat, "panel_v": panel,
            "battery": int(carga) if carga is not None else None, "ts": ts, "rssi": rssi,
        }))

    if d.get("nombre"):
        events.append((config.rx_topic("info", node), {
            "from": node, "long_name": str(d["nombre"])[:40], "short_name": None, "ts": ts,
        }))

    if tipo == "MSG" and str(d.get("msg", "")).strip():
        events.append((config.rx_topic("msg", node), {
            "packet_id": d.get("id"), "from": node,
            "to": config.node_id(int(d["dest"])) if str(d.get("dest", "")).isdigit()
                  and int(d["dest"]) not in (config.GATEWAY_ADDRESS, config.BROADCAST_ADDRESS) else "^all",
            "channel": 0, "text": str(d["msg"]).strip(), "ts": ts, "rssi": rssi, "snr": None,
        }))

    if tipo == "POS":
        lat, lon = _num(d.get("lat")), _num(d.get("lon"))
        if (lat is None or lon is None) and d.get("msg"):  # alternativa: "lat,lon" en msg
            parts = str(d["msg"]).split(",")
            if len(parts) == 2:
                lat, lon = _num(parts[0]), _num(parts[1])
        if lat is not None and lon is not None:
            events.append((config.rx_topic("pos", node), {
                "from": node, "lat": lat, "lon": lon, "alt": _num(d.get("alt")), "ts": ts, "rssi": rssi,
            }))

    return events


def encode_tx(text: str, to: str | None) -> str | None:
    """Línea a escribir en el gateway, o None si el destino no es un nodo de radio."""
    if to in (None, "", "^all"):
        dest = config.BROADCAST_ADDRESS
    else:
        dest = config.node_address(to)
        if dest is None:
            return None  # p. ej. un teléfono conectado por Wi-Fi: el servidor ya se lo entrega
    return json.dumps({"dest": dest, "msg": text}, ensure_ascii=False) + "\n"
