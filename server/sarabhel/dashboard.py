"""Dashboard del puesto de mando: API REST + eventos en vivo (SSE) + mapa web."""
import asyncio
import csv
import io
import json
import secrets
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import config, db
from .bus import Bus

log = config.setup_logging("dashboard")
STATIC = Path(__file__).parent / "static"


class Hub:
    """Reparte los eventos del broker a cada navegador conectado."""

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[asyncio.Queue] = set()

    def forward(self, topic: str, payload: dict) -> None:  # hilo de paho
        if self.loop is not None:
            self.loop.call_soon_threadsafe(self._fanout, topic.split("/", 1)[1], payload)

    def _fanout(self, kind: str, payload: dict) -> None:
        for q in list(self.clients):
            try:
                q.put_nowait((kind, payload))
            except asyncio.QueueFull:
                pass  # cliente lento: pierde eventos, pero recarga datos al reconectar


hub = Hub()
bus = Bus("dashboard")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.connect().close()  # crea el esquema si el dashboard arranca primero
    hub.loop = asyncio.get_running_loop()
    bus.subscribe("events/#", hub.forward)
    # Conectar al broker en segundo plano: la web (y la descarga de la app) debe
    # responder aunque el broker todavía no esté arriba.
    threading.Thread(target=bus.start, daemon=True, name="mqtt-connect").start()
    yield
    bus.stop()


app = FastAPI(title="Sarabhel — Puesto de mando", lifespan=lifespan)
# La app móvil (Capacitor) carga desde su propio origen (http://localhost en Android)
# y consulta esta API por la red local del puesto de mando.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "PATCH"],
                   allow_headers=["Content-Type"])


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


class SendRequest(BaseModel):
    text: str = Field(min_length=1)
    to: str | None = None

    @field_validator("text")
    @classmethod
    def fits_lora(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El mensaje está vacío")
        if len(v.encode("utf-8")) > config.MAX_TEXT_BYTES:
            raise ValueError(f"Máximo {config.MAX_TEXT_BYTES} bytes por mensaje de radio")
        return v


NODE_ID = r"^![0-9a-f]{8}$"


class DeviceHello(BaseModel):
    node_id: str = Field(pattern=NODE_ID)
    long_name: str = Field(min_length=1, max_length=40)
    short_name: str | None = Field(default=None, max_length=4)


class DeviceText(SendRequest):
    node_id: str = Field(pattern=NODE_ID)
    # Ubicación GPS del teléfono al enviar (SOS); va aparte para no gastar bytes del texto.
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class DevicePosition(BaseModel):
    node_id: str = Field(pattern=NODE_ID)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    alt: float | None = None


def _require_bus() -> None:
    if not bus.client.is_connected():
        raise HTTPException(503, "Broker no disponible")


# --- Teléfonos conectados por Wi-Fi (modo Campo "Red local") ---------------
# Un teléfono en el Wi-Fi del puesto de mando actúa como un nodo más: sus mensajes
# entran al bus igual que los que llegan por radio, así que se clasifican, se
# guardan y se reparten a los demás teléfonos y al puesto de mando.
@app.post("/api/device/hello")
def device_hello(req: DeviceHello):
    _require_bus()
    bus.publish(config.rx_topic("info", req.node_id), {"from": req.node_id, "long_name": req.long_name,
                                     "short_name": req.short_name or req.long_name[:4].upper(),
                                     "ts": db.now()})
    return {"status": "ok"}


@app.post("/api/device/text")
def device_text(req: DeviceText):
    _require_bus()
    packet_id = secrets.randbits(31)
    bus.publish(config.rx_topic("msg", req.node_id), {
        "packet_id": packet_id, "from": req.node_id, "to": req.to or "^all", "channel": 0, "text": req.text,
        "lat": req.lat, "lon": req.lon, "ts": db.now(), "rssi": None, "snr": None})
    return {"packet_id": packet_id}


@app.post("/api/device/position")
def device_position(req: DevicePosition):
    _require_bus()
    bus.publish(config.rx_topic("pos", req.node_id), {"from": req.node_id, "lat": req.lat, "lon": req.lon,
                                     "alt": req.alt, "ts": db.now()})
    return {"status": "ok"}


@app.get("/api/config")
def get_config():
    return {"tile_url": config.TILE_URL, "center": config.MAP_CENTER, "max_text_bytes": config.MAX_TEXT_BYTES,
            "energy": {"battery_wh": config.NODE_BATTERY_WH, "consumption_w": config.NODE_CONSUMPTION_W,
                       "dod": config.BATTERY_DOD, "low_pct": config.LOW_BATTERY_PCT}}


@app.get("/api/nodes")
def get_nodes():
    return query("SELECT * FROM nodes ORDER BY last_heard DESC")


@app.get("/api/messages")
def get_messages(limit: int = Query(100, ge=1, le=1000)):
    return query(
        """SELECT m.*, n.long_name FROM messages m
           LEFT JOIN nodes n ON n.node_id = m.from_node
           ORDER BY m.ts DESC, m.id DESC LIMIT ?""", (limit,))


@app.get("/api/positions/{node_id}")
def get_positions(node_id: str, limit: int = Query(200, ge=1, le=5000)):
    rows = query("SELECT lat, lon, alt, ts FROM positions WHERE node_id = ? ORDER BY ts DESC LIMIT ?",
                 (node_id, limit))
    return list(reversed(rows))


# --- Gestión de alertas -------------------------------------------------------
class AlertUpdate(BaseModel):
    estado: str | None = Field(default=None, pattern="^(nueva|en_atencion|atendida)$")
    equipo: str | None = Field(default=None, max_length=60)
    nota: str | None = Field(default=None, max_length=300)


@app.get("/api/alerts")
def get_alerts(limit: int = Query(100, ge=1, le=1000)):
    """Alertas recientes: primero las pendientes (nueva, en atención), luego las atendidas."""
    return query(
        """SELECT * FROM alerts ORDER BY
             CASE estado WHEN 'nueva' THEN 0 WHEN 'en_atencion' THEN 1 ELSE 2 END, ts DESC
           LIMIT ?""", (limit,))


@app.patch("/api/alerts/{alert_id}")
def update_alert(alert_id: int, req: AlertUpdate):
    changes = req.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(400, "Nada que actualizar")
    conn = db.connect()
    try:
        with conn:
            sets = ", ".join(f"{k} = ?" for k in changes)
            cur = conn.execute(f"UPDATE alerts SET {sets}, updated_ts = ? WHERE id = ?",
                               (*changes.values(), db.now(), alert_id))
            if cur.rowcount == 0:
                raise HTTPException(404, "Alerta no encontrada")
            row = dict(conn.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone())
    finally:
        conn.close()
    # Avisar a todos los dashboards y apps conectados.
    if bus.client.is_connected():
        bus.publish(config.EV_ALERT_UPDATE, row)
    else:
        hub.forward(config.EV_ALERT_UPDATE, row)
    return row


# --- Exportar reportes (CSV, para entregar a las autoridades) -----------------
def _csv(rows: list[dict], columns: list[str], filename: str) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c) if c != "fecha" else _fecha(r.get("ts")) for c in columns])
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _fecha(ts) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""


@app.get("/api/export/mensajes.csv")
def export_messages():
    rows = query("""SELECT m.*, n.long_name FROM messages m LEFT JOIN nodes n ON n.node_id = m.from_node
                    ORDER BY m.ts""")
    return _csv(rows, ["fecha", "direction", "from_node", "long_name", "to_node", "priority", "text", "lat", "lon"],
                "mensajes.csv")


@app.get("/api/export/alertas.csv")
def export_alerts():
    rows = query("SELECT * FROM alerts ORDER BY ts")
    return _csv(rows, ["fecha", "type", "node_id", "long_name", "text", "zone", "battery", "lat", "lon",
                       "estado", "equipo", "nota"], "alertas.csv")


@app.get("/api/zones")
def get_zones():
    path = Path(config.ZONES_FILE)
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/send", status_code=202)
def send(req: SendRequest):
    if not bus.client.is_connected():
        raise HTTPException(503, "Broker no disponible")
    bus.publish(config.APP_SEND, {"text": req.text, "to": req.to})
    return {"status": "en cola"}


@app.get("/api/stream")
async def stream():
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    hub.clients.add(q)

    async def events():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    kind, payload = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            hub.clients.discard(q)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


# --- Descarga de la app móvil sin internet --------------------------------
# Los teléfonos se conectan al Wi-Fi del puesto de mando y abren /descargar.
@app.get("/descargar")
def download_page():
    page = Path(config.WEB_DIR) / "index.html"
    if not page.exists():
        raise HTTPException(404, "Página de descarga no instalada (falta web/index.html)")
    return FileResponse(page)


@app.api_route(f"/descargar/{config.APK_NAME}", methods=["GET", "HEAD"])
def download_apk():
    apk = Path(config.DOWNLOADS_DIR) / config.APK_NAME
    if not apk.exists():
        raise HTTPException(404, f"Copia el APK en {config.DOWNLOADS_DIR}/{config.APK_NAME}")
    return FileResponse(apk, media_type="application/vnd.android.package-archive", filename=config.APK_NAME)


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main() -> None:
    uvicorn.run(app, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, log_level="warning")


if __name__ == "__main__":
    main()
