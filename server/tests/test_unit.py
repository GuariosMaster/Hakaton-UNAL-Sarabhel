import json

from sarabhel import config, geo
from sarabhel.gateway import encode_tx, parse_line
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
