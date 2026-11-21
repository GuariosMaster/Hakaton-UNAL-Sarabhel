import sqlite3
import unittest

from sarabhel import config, db, geo
from sarabhel.listener import nodedb_to_events, packet_to_events
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


if __name__ == "__main__":
    unittest.main()
