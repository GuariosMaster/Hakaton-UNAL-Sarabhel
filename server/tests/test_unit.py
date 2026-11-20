from sarabhel import config, geo
from sarabhel.listener import packet_to_events
from sarabhel.priority import CRITICO, INFORMATIVO, MODERADO, classify


def test_classify_critical():
    assert classify("SOS hay personas atrapadas") == CRITICO
    assert classify("Tenemos un HERIDO grave") == CRITICO
    assert classify("Olor a gas en la calle") == CRITICO
    assert classify("Hubo un derrumbe") == CRITICO


def test_classify_moderate_and_info():
    assert classify("Necesitamos agua potable") == MODERADO
    assert classify("Evacuando la cuadra") == MODERADO
    assert classify("Todos bien, llegamos") == INFORMATIVO
    # "sos" solo como palabra completa
    assert classify("Hay que sostener la puerta") == INFORMATIVO


def test_text_packet():
    pkt = {"id": 7, "fromId": "!abc", "toId": "^all", "rxTime": 100, "rxRssi": -90, "rxSnr": 5.5,
           "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "hola"}}
    [(topic, p)] = packet_to_events(pkt)
    assert topic == config.RX_TEXT
    assert p["from"] == "!abc" and p["text"] == "hola" and p["ts"] == 100 and p["rssi"] == -90


def test_position_packet():
    pkt = {"fromId": "!abc", "rxTime": 100,
           "decoded": {"portnum": "POSITION_APP", "position": {"latitude": 5.07, "longitude": -75.51, "time": 90}}}
    [(topic, p)] = packet_to_events(pkt)
    assert topic == config.RX_POSITION
    assert (p["lat"], p["lon"], p["ts"]) == (5.07, -75.51, 90)


def test_ignored_packets():
    assert packet_to_events({"fromId": "!abc", "decoded": {"portnum": "POSITION_APP", "position": {}}}) == []
    assert packet_to_events({"fromId": "!abc", "encrypted": "xxx"}) == []
    assert packet_to_events({"decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "x"}}) == []


def test_zones():
    zones = geo.load_zones(config.ZONES_FILE)
    assert zones
    assert geo.find_zone(zones, 5.0595, -75.4985) is not None  # dentro de la zona de ejemplo Aranjuez
    assert geo.find_zone(zones, 5.0689, -75.5174) is None      # centro de Manizales


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
