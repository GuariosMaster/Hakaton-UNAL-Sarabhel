"""Dashboard del puesto de mando: API REST + eventos en vivo (SSE) + mapa web."""
import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
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
            kind = config.SSE_KINDS.get(topic, topic.split("/", 1)[-1])
            self.loop.call_soon_threadsafe(self._fanout, kind, payload)

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
    bus.subscribe(config.EV_NODE, hub.forward)
    await asyncio.to_thread(bus.start)
    yield
    bus.stop()


app = FastAPI(title="Sarabhel — Puesto de mando", lifespan=lifespan)


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
            raise ValueError(f"Máximo {config.MAX_TEXT_BYTES} bytes por mensaje LoRa")
        return v


@app.get("/api/config")
def get_config():
    return {"tile_url": config.TILE_URL, "center": config.MAP_CENTER,
            "max_text_bytes": config.MAX_TEXT_BYTES,
            "mesh_connection": config.MESH_CONNECTION,
            "demo": config.is_demo_mode()}


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


app.mount("/static", StaticFiles(directory=STATIC), name="static")


def main() -> None:
    uvicorn.run(app, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT, log_level="warning")


if __name__ == "__main__":
    main()
