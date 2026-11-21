"""Nodo de albergue simulado: imita en el PC la API HTTP y el portal del firmware ESP32.

Sirve para probar la app móvil (conexión "Wi-Fi del albergue") y el portal sin hardware.
Si hay un broker MQTT del servidor, los mensajes "viajan por radio": se publican como si
los recibiera el gateway, y lo que el puesto de mando envía a este nodo aparece en el portal.

    python firmware/herramientas/nodo_simulado.py --nodo 2 --nombre "Albergue Coliseo" --puerto 8765

Luego abrir http://localhost:8765 (portal) o usar esa dirección en la app.
"""
import argparse
import json
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

FIRMWARE = Path(__file__).resolve().parent.parent
MAX_TEXTO = 36


def portal_html() -> str:
    """Extrae la página del portal de firmware/src/nodo/portal.h (la misma que sirve el ESP32)."""
    src = (FIRMWARE / "src" / "nodo" / "portal.h").read_text(encoding="utf-8")
    m = re.search(r'R"HTML\((.*)\)HTML"', src, re.S)
    return m.group(1) if m else "<h1>portal.h no encontrado</h1>"


class Nodo:
    def __init__(self, nodo: int, nombre: str, mqtt_host: str | None):
        self.nodo, self.nombre = nodo, nombre
        self.mensajes: list[dict] = []
        self.seq = 0
        self.lock = threading.Lock()
        self.carga = random.uniform(55, 95)
        self.inicio = time.time()
        self.mqtt = None
        if mqtt_host:
            self._conectar_mqtt(mqtt_host)
        self.guardar(nodo, nodo, "Nodo encendido", True)

    # --- energía simulada -------------------------------------------------
    def energia(self) -> dict:
        h = time.localtime().tm_hour + time.localtime().tm_min / 60
        sol = max(0.0, __import__("math").sin(3.14159 * (h - 6) / 12)) if 6 <= h <= 18 else 0.0
        self.carga = min(100, max(3, self.carga + (sol * 0.3 - 0.1)))
        return {"bat": round(12 + self.carga / 100 * 1.6, 2), "panel": round(sol * 18.2, 1), "carga": int(self.carga)}

    def guardar(self, de: int, para: int, msg: str, propio: bool) -> int:
        with self.lock:
            self.seq += 1
            self.mensajes.append({"seq": self.seq, "de": de, "para": para, "propio": propio,
                                  "t": time.time(), "msg": msg})
            self.mensajes = self.mensajes[-30:]
            return self.seq

    # --- "radio" a través del broker del servidor --------------------------
    def _conectar_mqtt(self, host: str) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            print("paho-mqtt no instalado: el nodo funciona sin conectarse al servidor")
            return
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"nodo-simulado-{self.nodo}")

        def on_connect(cl, *_):
            cl.subscribe("red/tx/msg", qos=1)
            self.radio("INFO", nombre=self.nombre)
            self.radio("TEL")
            print(f"[nodo {self.nodo}] conectado al broker {host} (simula la radio FSK)")

        def on_message(_cl, _u, m):
            p = json.loads(m.payload)
            to = p.get("to")
            if to in (None, "", "^all", f"nodo-{self.nodo}"):
                self.guardar(1, self.nodo, p["text"], False)

        c.on_connect, c.on_message = on_connect, on_message
        try:
            c.connect(host, 1883, 30)
            c.loop_start()
            self.mqtt = c
        except OSError as e:
            print(f"Sin broker en {host} ({e}): el nodo funciona sin conectarse al servidor")

    def radio(self, tipo: str, msg: str | None = None, **extra) -> bool:
        """Publica lo que el gateway entregaría al servidor por USB."""
        if not self.mqtt:
            return True
        node = f"nodo-{self.nodo}"
        e = self.energia()
        ts = int(time.time())
        self.mqtt.publish(f"red/albergue/{node}/tel", json.dumps(
            {"from": node, "voltage": e["bat"], "panel_v": e["panel"], "battery": e["carga"], "ts": ts, "rssi": -70}))
        if tipo == "INFO":
            self.mqtt.publish(f"red/albergue/{node}/info", json.dumps(
                {"from": node, "long_name": extra["nombre"], "short_name": None, "ts": ts}))
        elif tipo == "POS":
            self.mqtt.publish(f"red/albergue/{node}/pos", json.dumps(
                {"from": node, "lat": extra["lat"], "lon": extra["lon"], "alt": None, "ts": ts, "rssi": -70}))
        elif tipo == "MSG":
            self.mqtt.publish(f"red/albergue/{node}/msg", json.dumps(
                {"packet_id": None, "from": node, "to": "^all", "channel": 0, "text": msg, "ts": ts,
                 "rssi": -70, "snr": None}, ensure_ascii=False))
        return True


def handler_factory(nodo: Nodo):
    html = portal_html().encode("utf-8")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _json(self, code: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html)
            elif u.path == "/api/estado":
                self._json(200, {"nodo": nodo.nodo, "nombre": nodo.nombre, **nodo.energia(), "conectados": 1,
                                 "max_texto": MAX_TEXTO, "uptime": int(time.time() - nodo.inicio)})
            elif u.path == "/api/mensajes":
                desde = int(parse_qs(u.query).get("desde", ["0"])[0] or 0)
                with nodo.lock:
                    items = [{**{k: v for k, v in m.items() if k != "t"}, "hace": int(time.time() - m["t"])}
                             for m in nodo.mensajes if m["seq"] > desde]
                    self._json(200, {"ultimo": nodo.seq, "mensajes": items})
            else:  # portal cautivo: cualquier otra URL lleva al portal
                self.send_response(302)
                self.send_header("Location", "/")
                self.end_headers()

        def do_POST(self):
            u = urlparse(self.path)
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            except ValueError:
                return self._json(400, {"ok": False, "error": "JSON inválido"})
            if u.path == "/api/mensaje":
                msg = str(data.get("msg", "")).strip()
                if not msg or len(msg.encode("utf-8")) > MAX_TEXTO:
                    return self._json(400, {"ok": False, "error": f"El mensaje debe tener entre 1 y {MAX_TEXTO} bytes"})
                if data.get("lat") is not None and data.get("lon") is not None:
                    nodo.radio("POS", lat=float(data["lat"]), lon=float(data["lon"]))
                time.sleep(0.4)  # tiempo en el aire + confirmación RHMesh
                nodo.radio("MSG", msg)
                seq = nodo.guardar(nodo.nodo, int(data.get("dest") or 1), msg, True)
                print(f"[nodo {nodo.nodo}] TX por radio: {msg}")
                return self._json(200, {"ok": True, "seq": seq})
            if u.path == "/api/posicion":
                nodo.radio("POS", lat=float(data["lat"]), lon=float(data["lon"]))
                return self._json(200, {"ok": True})
            self._json(404, {"ok": False})

    return H


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nodo", type=int, default=2, help="dirección RHMesh (2-254)")
    ap.add_argument("--nombre", default="Albergue Coliseo")
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--mqtt", default="localhost", help="broker del servidor ('' = sin servidor)")
    a = ap.parse_args()
    nodo = Nodo(a.nodo, a.nombre, a.mqtt or None)
    srv = ThreadingHTTPServer(("0.0.0.0", a.puerto), handler_factory(nodo))
    print(f"Nodo simulado {a.nodo} \"{a.nombre}\" en http://localhost:{a.puerto}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
