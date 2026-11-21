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
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from . import config, db
from .auth import ROLES, Auth, AuthError
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
_auth: Auth | None = None


def get_auth() -> Auth:
    global _auth
    if _auth is None:
        _auth = Auth()
    return _auth


def need(*roles: str):
    """Dependencia: exige una sesión válida y uno de los roles indicados (todos si no se indica).
    El token va en la cabecera Authorization: Bearer … o, para enlaces y SSE, en ?token=…"""
    allowed = roles or ROLES

    def dep(authorization: str | None = Header(default=None), token: str | None = Query(default=None)) -> dict:
        tok = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else token
        try:
            user = get_auth().session(tok)
        except AuthError as e:
            raise HTTPException(e.status, e.message)
        if user["rol"] not in allowed:
            raise HTTPException(403, "Tu rol no tiene permiso para esta acción")
        return user

    return dep


ANY = need()
MANDO = need("admin", "mando")
ADMIN = need("admin")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.connect().close()  # crea el esquema si el dashboard arranca primero
    get_auth()            # crea las tablas de usuarios y el admin inicial
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
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "Authorization"])


@app.exception_handler(AuthError)
def _auth_error(_req: Request, exc: AuthError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status)


# --- Inicio de sesión ------------------------------------------------------------
class LoginRequest(BaseModel):
    usuario: str = Field(min_length=1, max_length=20)
    pin: str = Field(pattern=r"^\d{4}$")


class PinChange(BaseModel):
    actual: str = Field(pattern=r"^\d{4}$")
    nuevo: str = Field(pattern=r"^\d{4}$")


class UserCreate(BaseModel):
    usuario: str
    nombre: str = Field(min_length=1, max_length=40)
    rol: str
    pin: str = Field(pattern=r"^\d{4}$")
    equipo: str | None = Field(default=None, max_length=60)


class UserUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=40)
    rol: str | None = None
    equipo: str | None = Field(default=None, max_length=60)
    activo: bool | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4}$")


class RegisterRequest(BaseModel):
    usuario: str = Field(min_length=3, max_length=20)
    nombre: str = Field(min_length=1, max_length=40)
    pin: str = Field(pattern=r"^\d{4}$")
    equipo: str | None = Field(default=None, max_length=60)


@app.post("/api/auth/login")
def login(req: LoginRequest):
    return get_auth().login(req.usuario, req.pin)


@app.post("/api/auth/registro", status_code=201)
def register(req: RegisterRequest):
    """Crear cuenta propia (rol socorrista) y entrar de una vez."""
    return get_auth().register(req.usuario, req.nombre, req.pin, req.equipo)


@app.get("/api/auth/estado")
def auth_status():
    """Pública: si el registro está abierto y si el admin sigue con el PIN inicial (primer uso)."""
    return get_auth().status()


@app.get("/api/auth/me")
def me(user: dict = Depends(ANY)):
    return user


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        get_auth().logout(authorization[7:])
    return {"status": "ok"}


@app.post("/api/auth/pin")
def change_pin(req: PinChange, user: dict = Depends(ANY)):
    get_auth().change_own_pin(user["usuario"], req.actual, req.nuevo)
    return {"status": "ok"}


# --- Usuarios (solo administrador) ---------------------------------------------
@app.get("/api/users")
def list_users(_u: dict = Depends(ADMIN)):
    return get_auth().list_users()


@app.post("/api/users", status_code=201)
def create_user(req: UserCreate, _u: dict = Depends(ADMIN)):
    return get_auth().create_user(req.usuario, req.nombre, req.rol, req.pin, req.equipo)


@app.patch("/api/users/{usuario}")
def update_user(usuario: str, req: UserUpdate, user: dict = Depends(ADMIN)):
    return get_auth().update_user(usuario, by=user["usuario"], **req.model_dump(exclude_none=True))


@app.delete("/api/users/{usuario}")
def delete_user(usuario: str, user: dict = Depends(ADMIN)):
    get_auth().delete_user(usuario, by=user["usuario"])
    return {"status": "ok"}


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
    def fits_fsk(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El mensaje está vacío")
        if len(v.encode("utf-8")) > config.USB_MAX_TEXT_BYTES:
            raise ValueError(
                f"Máximo {config.USB_MAX_TEXT_BYTES} bytes por mensaje; "
                f"el gateway lo fragmenta por aire en tramas de {config.RF_MAX_PAYLOAD_BYTES} bytes"
            )
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
def device_hello(req: DeviceHello, _u: dict = Depends(ANY)):
    _require_bus()
    bus.publish(config.rx_topic("info", req.node_id), {"from": req.node_id, "long_name": req.long_name,
                                     "short_name": req.short_name or req.long_name[:4].upper(),
                                     "ts": db.now()})
    return {"status": "ok"}


@app.post("/api/device/text")
def device_text(req: DeviceText, _u: dict = Depends(ANY)):
    _require_bus()
    packet_id = secrets.randbits(31)
    bus.publish(config.rx_topic("msg", req.node_id), {
        "packet_id": packet_id, "from": req.node_id, "to": req.to or "^all", "channel": 0, "text": req.text,
        "lat": req.lat, "lon": req.lon, "ts": db.now(), "rssi": None, "snr": None})
    return {"packet_id": packet_id}


@app.post("/api/device/position")
def device_position(req: DevicePosition, _u: dict = Depends(ANY)):
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
def get_nodes(_u: dict = Depends(ANY)):
    return query("SELECT * FROM nodes ORDER BY last_heard DESC")


@app.get("/api/messages")
def get_messages(limit: int = Query(100, ge=1, le=1000), _u: dict = Depends(ANY)):
    return query(
        """SELECT m.*, n.long_name FROM messages m
           LEFT JOIN nodes n ON n.node_id = m.from_node
           ORDER BY m.ts DESC, m.id DESC LIMIT ?""", (limit,))


@app.get("/api/gateways")
def get_gateways(_u: dict = Depends(ANY)):
    """Gateways con sus nodos escuchados en los últimos 30 min (mejor señal primero)."""
    limite = db.now() - 1800
    gws = query("SELECT * FROM gateways ORDER BY gateway_id")
    links = query("""SELECT e.*, n.long_name FROM enlaces e LEFT JOIN nodes n ON n.node_id = e.node_id
                     WHERE e.last_seen > ? ORDER BY e.rssi_prom DESC""", (limite,))
    for g in gws:
        g["enlaces"] = [l for l in links if l["gateway_id"] == g["gateway_id"]]
        g["nodos"] = len(g["enlaces"])
    return gws


@app.get("/api/enlaces")
def get_links(_u: dict = Depends(ANY)):
    """Enlaces nodo-gateway recientes (para dibujar la red y ver qué nodos dependen de un solo gateway)."""
    return query("""SELECT e.*, n.long_name, n.lat AS node_lat, n.lon AS node_lon, g.nombre AS gateway_nombre,
                           g.lat AS gw_lat, g.lon AS gw_lon
                    FROM enlaces e LEFT JOIN nodes n ON n.node_id = e.node_id
                    LEFT JOIN gateways g ON g.gateway_id = e.gateway_id
                    WHERE e.last_seen > ? ORDER BY e.node_id""", (db.now() - 1800,))


@app.get("/api/positions/{node_id}")
def get_positions(node_id: str, limit: int = Query(200, ge=1, le=5000), _u: dict = Depends(ANY)):
    rows = query("SELECT lat, lon, alt, ts FROM positions WHERE node_id = ? ORDER BY ts DESC LIMIT ?",
                 (node_id, limit))
    return list(reversed(rows))


# --- Gestión de alertas -------------------------------------------------------
class AlertUpdate(BaseModel):
    estado: str | None = Field(default=None, pattern="^(nueva|en_atencion|atendida)$")
    equipo: str | None = Field(default=None, max_length=60)
    nota: str | None = Field(default=None, max_length=300)


@app.get("/api/alerts")
def get_alerts(limit: int = Query(100, ge=1, le=1000), _u: dict = Depends(ANY)):
    """Alertas recientes: primero las pendientes (nueva, en atención), luego las atendidas."""
    return query(
        """SELECT * FROM alerts ORDER BY
             CASE estado WHEN 'nueva' THEN 0 WHEN 'en_atencion' THEN 1 ELSE 2 END, ts DESC
           LIMIT ?""", (limit,))


@app.patch("/api/alerts/{alert_id}")
def update_alert(alert_id: int, req: AlertUpdate, user: dict = Depends(ANY)):
    changes = req.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(400, "Nada que actualizar")
    conn = db.connect()
    try:
        if user["rol"] == "socorrista":
            row = conn.execute("SELECT equipo FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Alerta no encontrada")
            if not user.get("equipo") or (row["equipo"] or "").strip().lower() != user["equipo"].strip().lower():
                raise HTTPException(403, "Solo puedes actualizar las alertas asignadas a tu equipo")
            if "equipo" in changes:
                raise HTTPException(403, "Solo el puesto de mando asigna equipos")
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
def export_messages(_u: dict = Depends(MANDO)):
    rows = query("""SELECT m.*, n.long_name FROM messages m LEFT JOIN nodes n ON n.node_id = m.from_node
                    ORDER BY m.ts""")
    return _csv(rows, ["fecha", "direction", "from_node", "long_name", "to_node", "priority", "text", "lat", "lon"],
                "mensajes.csv")


@app.get("/api/export/alertas.csv")
def export_alerts(_u: dict = Depends(MANDO)):
    rows = query("SELECT * FROM alerts ORDER BY ts")
    return _csv(rows, ["fecha", "type", "node_id", "long_name", "text", "zone", "battery", "lat", "lon",
                       "estado", "equipo", "nota"], "alertas.csv")


@app.get("/api/zones")
def get_zones(_u: dict = Depends(ANY)):
    path = Path(config.ZONES_FILE)
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/send", status_code=202)
def send(req: SendRequest, _u: dict = Depends(MANDO)):
    if not bus.client.is_connected():
        raise HTTPException(503, "Broker no disponible")
    bus.publish(config.APP_SEND, {"text": req.text, "to": req.to})
    return {"status": "en cola"}


@app.get("/api/stream")
async def stream(_u: dict = Depends(ANY)):
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
