<<<<<<< HEAD
import json

from sarabhel import config, geo
from sarabhel.gateway import encode_tx, parse_line
=======
import sqlite3
import unittest

from sarabhel import config, db, geo
from sarabhel.listener import nodedb_to_events, packet_to_events
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9
from sarabhel.priority import CRITICO, INFORMATIVO, MODERADO, classify


class PriorityTests(unittest.TestCase):
    def test_classify_critical(self):
        for text in ("SOS hay personas atrapadas", "Tenemos un HERIDO grave",
                     "Olor a gas en la calle", "Hubo un derrumbe"):
            self.assertEqual(classify(text), CRITICO)

    def test_classify_moderate_and_info(self):
        for text in ("Necesitamos agua potable", "Evacuando la cuadra"):
            self.assertEqual(classify(text), MODERADO)
        for text in ("Todos bien, llegamos", "Hay que sostener la puerta"):
            self.assertEqual(classify(text), INFORMATIVO)


class PacketTests(unittest.TestCase):
    def test_text_packet(self):
        pkt = {"id": 7, "fromId": "!abc", "toId": "^all", "rxTime": 100, "rxRssi": -90, "rxSnr": 5.5,
               "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "hola"}}
        [(topic, p)] = packet_to_events(pkt)
        self.assertEqual(topic, config.RX_TEXT)
        self.assertEqual(p["packet_id"], 7)
        self.assertEqual((p["from"], p["text"], p["ts"], p["rssi"]), ("!abc", "hola", 100, -90))

    def test_position_packet(self):
        pkt = {"fromId": "!abc", "rxTime": 100,
               "decoded": {"portnum": "POSITION_APP", "position": {"latitude": 5.07, "longitude": -75.51, "time": 90}}}
        [(topic, p)] = packet_to_events(pkt)
        self.assertEqual(topic, config.RX_POSITION)
        self.assertEqual((p["lat"], p["lon"], p["ts"]), (5.07, -75.51, 90))

    def test_ignored_packets(self):
        self.assertEqual(packet_to_events({"fromId": "!abc", "decoded": {"portnum": "POSITION_APP", "position": {}}}), [])
        self.assertEqual(packet_to_events({"fromId": "!abc", "encrypted": "xxx"}), [])
        self.assertEqual(packet_to_events({"decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "x"}}), [])

    def test_nodedb_without_gps_still_reports_telemetry(self):
        events = nodedb_to_events({"!7996c8bb": {
            "user": {"longName": "Meshtastic c8bb", "shortName": "c8bb"},
            "position": {},
            "deviceMetrics": {"batteryLevel": 101, "voltage": 4.259},
            "lastHeard": 100,
        }})
        topics = [topic for topic, _ in events]
        self.assertIn(config.RX_NODEINFO, topics)
        self.assertIn(config.RX_TELEMETRY, topics)
        self.assertNotIn(config.RX_POSITION, topics)
        telemetry = [p for topic, p in events if topic == config.RX_TELEMETRY][0]
        self.assertEqual((telemetry["battery"], telemetry["voltage"]), (101, 4.259))


<<<<<<< HEAD
def test_gateway_msg_line():
    line = ('{"nodo":2,"tipo":"MSG","bat":12.4,"panel":18.1,"carga":82,'
            '"msg":"Albergue Coliseo: 280 personas","rssi":-72}')
    events = dict(parse_line(line))
    tel = events["red/albergue/nodo-2/tel"]
    assert (tel["voltage"], tel["panel_v"], tel["battery"], tel["rssi"]) == (12.4, 18.1, 82, -72)
    msg = events["red/albergue/nodo-2/msg"]
    assert msg["from"] == "nodo-2" and msg["text"] == "Albergue Coliseo: 280 personas" and msg["to"] == "^all"


def test_gateway_pos_and_info_lines():
    pos = dict(parse_line('{"nodo":3,"tipo":"POS","lat":5.07,"lon":-75.51}'))["red/albergue/nodo-3/pos"]
    assert (pos["lat"], pos["lon"]) == (5.07, -75.51)
    alt = dict(parse_line('{"nodo":3,"tipo":"POS","msg":"5.07,-75.51"}'))["red/albergue/nodo-3/pos"]
    assert (alt["lat"], alt["lon"]) == (5.07, -75.51)
    info = dict(parse_line('{"nodo":4,"tipo":"INFO","nombre":"Ladera Aranjuez"}'))
    assert info["red/albergue/nodo-4/info"]["long_name"] == "Ladera Aranjuez"


def test_gateway_ignores_noise():
    assert parse_line("[RHMesh] ruta actualizada") == []
    assert parse_line('{"tipo":"MSG","msg":"sin nodo"}') == []
    assert parse_line('{"nodo":300,"tipo":"MSG","msg":"fuera de rango"}') == []
    assert parse_line("{json roto") == []


def test_encode_tx():
    assert json.loads(encode_tx("Hola", "nodo-5")) == {"dest": 5, "msg": "Hola"}
    assert json.loads(encode_tx("Todos", None)) == {"dest": 255, "msg": "Todos"}
    assert encode_tx("Para un teléfono", "!a1b2c3d4") is None
=======
class ContractTests(unittest.TestCase):
    def test_canonical_topics(self):
        self.assertEqual(config.RX_TEXT, "lora/gateway/rx/text")
        self.assertEqual(config.TX_TEXT, "lora/gateway/tx")
        self.assertEqual(config.EV_NODE, "lora/nodes")
        self.assertEqual(config.SSE_KINDS[config.EV_NODE], "node")
        self.assertEqual(config.SSE_KINDS[config.EV_MESSAGE], "msg")

    def test_demo_flag_comes_from_connection_mode(self):
        self.assertTrue(config.is_demo_mode("sim"))
        self.assertFalse(config.is_demo_mode("serial"))
        self.assertFalse(config.is_demo_mode("tcp"))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(db.SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_packet_id_dedupe(self):
        self.assertFalse(db.is_duplicate_packet(self.conn, 42))
        self.conn.execute(
            "INSERT INTO messages (packet_id, direction, text, priority, ts) VALUES (?, 'in', ?, ?, ?)",
            (42, "SOS", "critico", 100),
        )
        self.assertTrue(db.is_duplicate_packet(self.conn, 42))
        self.assertFalse(db.is_duplicate_packet(self.conn, 43))
        self.assertFalse(db.is_duplicate_packet(self.conn, None))


class GeoTests(unittest.TestCase):
    def test_zones(self):
        zones = geo.load_zones(config.ZONES_FILE)
        self.assertTrue(zones)
        self.assertIsNotNone(geo.find_zone(zones, 5.0595, -75.4985))
        self.assertIsNone(geo.find_zone(zones, 5.0689, -75.5174))

    def test_valid_coords(self):
        self.assertTrue(geo.valid_coords(5.0, -75.0))
        for lat, lon in ((0, 0), (None, 1), (91, 0)):
            self.assertFalse(geo.valid_coords(lat, lon))
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9


class MessagingDedupeTests(unittest.TestCase):
    def test_repeated_packet_id_stores_one_message_and_emits_one_event(self):
        import sys
        import types
        from unittest.mock import patch

        paho = types.ModuleType("paho")
        mqtt = types.ModuleType("paho.mqtt")
        client = types.ModuleType("paho.mqtt.client")
        client.Client = lambda *a, **k: None
        client.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)
        client.topic_matches_sub = lambda pattern, topic: False
        mqtt.client = client
        paho.mqtt = mqtt
        with patch.dict(sys.modules, {"paho": paho, "paho.mqtt": mqtt,
                                      "paho.mqtt.client": client}):
            from sarabhel.messaging import MessagingService

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(db.SCHEMA)
        self.addCleanup(conn.close)

        class FakeBus:
            def __init__(self):
                self.published = []

            def publish(self, topic, payload, qos=1):
                self.published.append(topic)

        bus = FakeBus()
        with patch.object(db, "connect", return_value=conn):
            svc = MessagingService(bus)
        pkt = {"packet_id": 4242, "from": "!7996c8bb",
               "text": "SOS hay personas atrapadas", "ts": 100,
               "to": "^all", "channel": 0, "rssi": -90, "snr": 5.5}
        svc.on_text(config.RX_TEXT, pkt)
        svc.on_text(config.RX_TEXT, pkt)  # reintento de la malla
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM messages WHERE packet_id=4242").fetchone()[0], 1)
        self.assertEqual(bus.published.count(config.EV_MESSAGE), 1)
        self.assertEqual(bus.published.count(config.EV_ALERT), 1)


<<<<<<< HEAD
def test_coords_in_text():
    from sarabhel.messaging import coords_in_text
    assert coords_in_text("SOS Herido 📍5.07012,-75.51234") == (5.07012, -75.51234)
    assert coords_in_text("SOS sin ubicación") is None
    assert coords_in_text("📍0.0,0.0") is None


def test_valid_coords():
    assert geo.valid_coords(5.0, -75.0)
    assert not geo.valid_coords(0, 0)
    assert not geo.valid_coords(None, 1)
    assert not geo.valid_coords(91, 0)


def test_lineas_propias_del_gateway():
    # Con "gw":1 o sin rssi desde la dirección 1: es el estado del gateway, no un nodo
    [(topic, p)] = parse_line('{"gw":1,"nodo":1,"tipo":"TEL","bat":12.9,"panel":0.0,"carga":64}', "gw-2")
    assert topic == "red/gateway/gw-2/estado" and p["battery"] == 64 and p["estado"] == "conectado"
    [(topic, p)] = parse_line('{"nodo":1,"tipo":"INFO","nombre":"Puesto UNAL"}', "gw-1")
    assert topic == "red/gateway/gw-1/estado" and p["nombre"] == "Puesto UNAL"
    # Las tramas de nodos llevan el gateway por el que entraron
    events = parse_line('{"nodo":3,"tipo":"MSG","msg":"hola","rssi":-80}', "gw-2")
    assert all(p["gateway"] == "gw-2" for _, p in events)


def test_tablas_gateways_y_enlaces(tmp_path, monkeypatch):
    from sarabhel import db
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "gw.db"))
    conn = db.connect()
    with conn:
        db.upsert_gateway(conn, {"gateway_id": "gw-1", "estado": "conectado", "nombre": "Puesto UNAL"})
        db.upsert_gateway(conn, {"gateway_id": "gw-2", "estado": "conectado"})
        db.touch_link(conn, "nodo-6", "gw-1", -98, db.now())
        db.touch_link(conn, "nodo-6", "gw-2", -70, db.now())
    assert db.best_gateway(conn, "nodo-6") == "gw-2"          # mejor señal
    with conn:
        db.upsert_gateway(conn, {"gateway_id": "gw-2", "estado": "desconectado"})
    assert db.best_gateway(conn, "nodo-6") == "gw-1"          # el otro se cayó
    assert db.best_gateway(conn, "nodo-9") is None             # nadie lo oye


def test_simuladores_publican_tramas():
    """Regresión: el simulador normal y el escenario deben poder emitir tramas por sus gateways."""
    from sarabhel.simulator import Escenario, Simulator

    class BusFalso:
        def __init__(self):
            self.temas = []

        def publish(self, topic, payload, qos=1):
            self.temas.append(topic)

    for cls in (Simulator, Escenario):
        bus = BusFalso()
        sim = cls(bus)
        sim.gateway_status()
        sim._emit({"nodo": 6, "tipo": "MSG", **sim._energy(6), "msg": "prueba"})
        assert "red/gateway/gw-1/estado" in bus.temas
        assert bus.temas.count("red/albergue/nodo-6/msg") == 2  # lo oyen los dos gateways simulados
=======
if __name__ == "__main__":
    unittest.main()
>>>>>>> 660dcf222dfc98eb9534afaed0f07a25bcd489f9
