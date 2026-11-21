"""Base de datos SQLite compartida (modo WAL para varios procesos)."""
import os
import sqlite3
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id     TEXT PRIMARY KEY,
    long_name   TEXT,
    short_name  TEXT,
    lat         REAL,
    lon         REAL,
    alt         REAL,
    pos_ts      INTEGER,
    battery     INTEGER,          -- carga de la batería (%)
    voltage     REAL,             -- voltaje de la batería (V)
    panel_v     REAL,             -- voltaje del panel solar (V)
    energy_ts   INTEGER,          -- última telemetría de energía
    rssi        REAL,             -- intensidad de la última trama recibida por el gateway
    last_heard  INTEGER,
    risk_zone   TEXT,
    alert_ts    INTEGER
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    packet_id   INTEGER,
    direction   TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    from_node   TEXT,
    to_node     TEXT,
    channel     INTEGER,
    text        TEXT NOT NULL,
    priority    TEXT NOT NULL,
    lat         REAL,
    lon         REAL,
    rssi        REAL,
    snr         REAL,
    ts          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ts ON messages (ts);

CREATE TABLE IF NOT EXISTS positions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id  TEXT NOT NULL,
    lat      REAL NOT NULL,
    lon      REAL NOT NULL,
    alt      REAL,
    ts       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_positions_node_ts ON positions (node_id, ts);

-- Alertas y su gestión en el puesto de mando
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,              -- mensaje_critico | zona_riesgo | bateria_baja
    node_id     TEXT,
    long_name   TEXT,
    text        TEXT,
    zone        TEXT,
    battery     INTEGER,
    lat         REAL,
    lon         REAL,
    ts          INTEGER NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'nueva' CHECK (estado IN ('nueva', 'en_atencion', 'atendida')),
    equipo      TEXT,                       -- equipo de rescate asignado
    nota        TEXT,
    updated_ts  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts (ts);

-- Gateways (ESP32-S3 + RFM69HCW) que conectan la malla de radio con el servidor
CREATE TABLE IF NOT EXISTS gateways (
    gateway_id    TEXT PRIMARY KEY,       -- p. ej. "gw-1"
    nombre        TEXT,                   -- p. ej. "Puesto de mando UNAL"
    direccion     INTEGER,                -- dirección RHMesh del gateway en la malla
    conexion      TEXT,                   -- cómo llega al servidor: "usb:COM5", "usb:/dev/ttyACM0", "sim"
    estado        TEXT NOT NULL DEFAULT 'desconectado' CHECK (estado IN ('conectado', 'desconectado')),
    lat           REAL,
    lon           REAL,
    battery       INTEGER,                -- energía del kit del gateway (%)
    voltage       REAL,
    panel_v       REAL,
    nodos         INTEGER DEFAULT 0,      -- nodos escuchados en los últimos 30 min (lo calcula la API)
    conectado_ts  INTEGER,                -- desde cuándo está conectado
    last_seen     INTEGER,                -- última línea recibida de este gateway
    creado_ts     INTEGER NOT NULL
);

-- Qué gateway escucha a qué nodo y con qué señal: sirve para responder por el mejor
-- gateway, ver qué albergues dependen de uno solo y dibujar la red.
CREATE TABLE IF NOT EXISTS enlaces (
    node_id     TEXT NOT NULL,
    gateway_id  TEXT NOT NULL,
    rssi        REAL,                     -- última intensidad (dBm)
    rssi_prom   REAL,                     -- promedio móvil de la intensidad
    tramas      INTEGER NOT NULL DEFAULT 0,
    last_seen   INTEGER NOT NULL,
    PRIMARY KEY (node_id, gateway_id)
);
CREATE INDEX IF NOT EXISTS idx_enlaces_gateway ON enlaces (gateway_id);
"""

# Si dos gateways reciben la misma trama, el segundo aviso llega a los pocos segundos.
DUPLICATE_WINDOW_SECS = 30


def upsert_gateway(conn: sqlite3.Connection, g: dict) -> dict:
    """Crea o actualiza un gateway con los campos presentes en `g` (estado, energía, nombre…)."""
    ts = now()
    gid = g["gateway_id"]
    prev = conn.execute("SELECT * FROM gateways WHERE gateway_id = ?", (gid,)).fetchone()
    if prev is None:
        conn.execute("INSERT INTO gateways (gateway_id, creado_ts) VALUES (?, ?)", (gid, ts))
    fields = {k: g[k] for k in ("nombre", "direccion", "conexion", "estado", "lat", "lon", "battery", "voltage",
                                "panel_v") if g.get(k) is not None}
    if g.get("estado") == "conectado" and (prev is None or prev["estado"] != "conectado"):
        fields["conectado_ts"] = ts
    fields["last_seen"] = ts
    conn.execute(f"UPDATE gateways SET {', '.join(f'{k} = ?' for k in fields)} WHERE gateway_id = ?",
                 (*fields.values(), gid))
    return dict(conn.execute("SELECT * FROM gateways WHERE gateway_id = ?", (gid,)).fetchone())


def touch_link(conn: sqlite3.Connection, node_id: str, gateway_id: str, rssi: float | None, ts: int) -> None:
    """Registra que `gateway_id` escuchó a `node_id` (con promedio móvil de la señal)."""
    conn.execute(
        """INSERT INTO enlaces (node_id, gateway_id, rssi, rssi_prom, tramas, last_seen) VALUES (?, ?, ?, ?, 1, ?)
           ON CONFLICT(node_id, gateway_id) DO UPDATE SET
             rssi = COALESCE(excluded.rssi, rssi),
             rssi_prom = CASE WHEN excluded.rssi IS NULL THEN rssi_prom
                              WHEN rssi_prom IS NULL THEN excluded.rssi
                              ELSE rssi_prom * 0.8 + excluded.rssi * 0.2 END,
             tramas = tramas + 1,
             last_seen = MAX(last_seen, excluded.last_seen)""",
        (node_id, gateway_id, rssi, rssi, ts))


def best_gateway(conn: sqlite3.Connection, node_id: str, max_age_secs: int = 1800) -> str | None:
    """Gateway conectado que mejor escucha al nodo recientemente (mejor señal promedio)."""
    row = conn.execute(
        """SELECT e.gateway_id FROM enlaces e JOIN gateways g ON g.gateway_id = e.gateway_id
           WHERE e.node_id = ? AND g.estado = 'conectado' AND e.last_seen > ?
           ORDER BY COALESCE(e.rssi_prom, -200) DESC, e.last_seen DESC LIMIT 1""",
        (node_id, now() - max_age_secs)).fetchone()
    return row["gateway_id"] if row else None

ALERT_FIELDS = ("type", "node_id", "long_name", "text", "zone", "battery", "lat", "lon", "ts")


def create_alert(conn: sqlite3.Connection, alert: dict) -> dict:
    """Guarda una alerta nueva y devuelve el registro completo (con id y estado)."""
    row = {k: alert.get(k) for k in ALERT_FIELDS}
    row["node_id"] = row["node_id"] or alert.get("from_node")
    row["ts"] = row["ts"] or now()
    cur = conn.execute(
        f"INSERT INTO alerts ({', '.join(ALERT_FIELDS)}) VALUES ({', '.join('?' * len(ALERT_FIELDS))})",
        tuple(row[k] for k in ALERT_FIELDS))
    return dict(conn.execute("SELECT * FROM alerts WHERE id = ?", (cur.lastrowid,)).fetchone())


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(config.DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    # Migración de bases creadas antes de la telemetría de energía.
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(nodes)")}
    for col, kind in (("panel_v", "REAL"), ("energy_ts", "INTEGER"), ("rssi", "REAL")):
        if col not in cols:
            conn.execute(f"ALTER TABLE nodes ADD COLUMN {col} {kind}")
    # Mensajes: por qué gateway entraron (bases anteriores a varios gateways).
    if "gateway_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(messages)")}:
        conn.execute("ALTER TABLE messages ADD COLUMN gateway_id TEXT")
    conn.commit()
    return conn


def now() -> int:
    return int(time.time())


def touch_node(conn: sqlite3.Connection, node_id: str, ts: int) -> None:
    """Crea el nodo si no existe y actualiza 'última vez escuchado'."""
    conn.execute(
        """INSERT INTO nodes (node_id, last_heard) VALUES (?, ?)
           ON CONFLICT(node_id) DO UPDATE SET last_heard = MAX(COALESCE(last_heard, 0), excluded.last_heard)""",
        (node_id, ts),
    )
