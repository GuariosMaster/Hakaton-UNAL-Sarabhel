"""Configuración por variables de entorno y nombres de temas del bus."""
import logging
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


MQTT_HOST = _env("MQTT_HOST", "localhost")
MQTT_PORT = int(_env("MQTT_PORT", "1883"))

DB_PATH = _env("DB_PATH", str(BASE_DIR / "data" / "sarabhel.db"))
ZONES_FILE = _env("ZONES_FILE", str(BASE_DIR / "zones" / "zonas_riesgo.geojson"))

# sim | serial | tcp
MESH_CONNECTION = _env("MESH_CONNECTION", "sim").lower()
MESH_SERIAL_PORT = _env("MESH_SERIAL_PORT") or None  # None = autodetectar
MESH_TCP_HOST = _env("MESH_TCP_HOST")
MESH_CHANNEL_INDEX = int(_env("MESH_CHANNEL_INDEX", "0"))

SIM_INTERVAL_SECS = float(_env("SIM_INTERVAL_SECS", "6"))

DASHBOARD_HOST = _env("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(_env("DASHBOARD_PORT", "8080"))
TILE_URL = _env("TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAP_CENTER = (5.0689, -75.5174)  # Manizales

# Límite práctico de un mensaje de texto Meshtastic (bytes UTF-8).
MAX_TEXT_BYTES = 200

# --- Temas MQTT -------------------------------------------------------------
# Contrato canónico acordado para el tráfico de radio.
# Radio -> servidor (publica el listener)
RX_TEXT = "lora/gateway/rx/text"
RX_POSITION = "lora/gateway/rx/position"
RX_NODEINFO = "lora/gateway/rx/nodeinfo"
RX_TELEMETRY = "lora/gateway/rx/telemetry"
# Servidor -> radio (escucha el listener)
TX_TEXT = "lora/gateway/tx"
# Petición de envío desde el dashboard (la procesa el servicio de mensajería)
APP_SEND = "app/send"
# Eventos ya procesados y guardados (los consume el dashboard).
# lora/nodes es el tema canónico del estado de nodos; los demás son internos.
EV_MESSAGE = "events/msg"
EV_POSITION = "events/position"
EV_NODE = "lora/nodes"
EV_ALERT = "events/alert"

# El tipo de evento SSE no debe depender del prefijo del tema MQTT.
SSE_KINDS = {
    EV_MESSAGE: "msg",
    EV_POSITION: "position",
    EV_NODE: "node",
    EV_ALERT: "alert",
}


def is_demo_mode(mode: str | None = None) -> bool:
    """True cuando los datos provienen del simulador, no del gateway real."""
    return (mode if mode is not None else MESH_CONNECTION) == "sim"


def setup_logging(service: str) -> logging.Logger:
    logging.basicConfig(
        level=_env("LOG_LEVEL", "INFO").upper(),
        format=f"%(asctime)s [{service}] %(levelname)s %(message)s",
    )
    return logging.getLogger(service)
