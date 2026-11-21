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

# Conexión con el gateway ESP32-S3 + RFM69HCW: sim (simulado) | usb (puerto serie)
MESH_CONNECTION = _env("MESH_CONNECTION", "sim").lower()
MESH_USB_DEVICE = _env("MESH_USB_DEVICE") or None  # None = autodetectar (COM5, /dev/ttyACM0…)
MESH_USB_BAUD = int(_env("MESH_USB_BAUD", "115200"))

SIM_INTERVAL_SECS = float(_env("SIM_INTERVAL_SECS", "6"))

# Red FSK (RadioHead RHMesh): direcciones 1-254; 1 es el gateway del puesto de mando.
GATEWAY_ADDRESS = 1
BROADCAST_ADDRESS = 255

# Alerta cuando la batería de un nodo baja de este porcentaje.
LOW_BATTERY_PCT = int(_env("LOW_BATTERY_PCT", "20"))

DASHBOARD_HOST = _env("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(_env("DASHBOARD_PORT", "8080"))
TILE_URL = _env("TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAP_CENTER = (5.0689, -75.5174)  # Manizales

# Página de descarga de la app (carpeta web/ del repositorio) y carpeta con el APK.
WEB_DIR = _env("WEB_DIR", str(BASE_DIR.parent / "web"))
DOWNLOADS_DIR = _env("DOWNLOADS_DIR", str(BASE_DIR / "descargas"))
APK_NAME = "RedEmergencia.apk"

# Texto máximo por mensaje (bytes UTF-8). Un paquete RHMesh sobre RFM69 lleva como
# máximo 54 bytes; la trama "MSG|12.4|18.1|100|" ocupa 18, quedan 36 para el texto.
MAX_TEXT_BYTES = int(_env("MAX_TEXT_BYTES", "36"))

# --- Temas MQTT -------------------------------------------------------------
# Red -> servidor: red/albergue/{nodo_id}/{msg|tel|pos|info}
# Los publica el listener (nodos por radio) y el dashboard (teléfonos por Wi-Fi).
RX_TEXT = "red/albergue/+/msg"
RX_TELEMETRY = "red/albergue/+/tel"
RX_POSITION = "red/albergue/+/pos"
RX_NODEINFO = "red/albergue/+/info"
# Servidor -> radio (escucha el listener)
TX_TEXT = "red/tx/msg"


def rx_topic(kind: str, node_id: str) -> str:
    """Tema concreto donde publicar, p. ej. rx_topic("msg", "nodo-2")."""
    return f"red/albergue/{node_id}/{kind}"


def node_id(address: int) -> str:
    """Id de un nodo de radio en el servidor: dirección RHMesh 2 -> 'nodo-2'."""
    return f"nodo-{address}"


def node_address(node: str | None) -> int | None:
    """Dirección RHMesh de un id 'nodo-N'; None si no es un nodo de radio (p. ej. un teléfono)."""
    if node and node.startswith("nodo-") and node[5:].isdigit():
        n = int(node[5:])
        return n if 1 <= n <= 254 else None
    return None
# Petición de envío desde el dashboard (la procesa el servicio de mensajería)
APP_SEND = "app/send"
# Eventos ya procesados y guardados (los consume el dashboard)
EV_MESSAGE = "events/msg"
EV_POSITION = "events/position"
EV_NODE = "events/node"
EV_ALERT = "events/alert"


def setup_logging(service: str) -> logging.Logger:
    logging.basicConfig(
        level=_env("LOG_LEVEL", "INFO").upper(),
        format=f"%(asctime)s [{service}] %(levelname)s %(message)s",
    )
    return logging.getLogger(service)
