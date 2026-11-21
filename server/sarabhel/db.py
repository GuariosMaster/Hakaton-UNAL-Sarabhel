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
"""

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
