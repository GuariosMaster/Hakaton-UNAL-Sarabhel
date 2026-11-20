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
    battery     INTEGER,
    voltage     REAL,
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
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(config.DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
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
