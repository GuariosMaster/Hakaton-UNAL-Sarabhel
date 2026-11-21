import json
import urllib.error

from sarabhel import config, db, triage
from sarabhel.priority import CRITICO, INFORMATIVO, MODERADO


class FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def publish(self, topic: str, payload: dict, qos: int = 1) -> None:
        self.events.append((topic, payload))


def test_parse_llm_response_normalizes_synonyms_and_markdown():
    raw = """```json
    {
      "categoria": "res",
      "subcategoria": "Colapso con atrapados",
      "prioridad": "Alta",
      "necesidades": ["camillas", "equipo de corte"],
      "resumen": "Tres personas atrapadas tras colapso"
    }
    ```"""
    parsed = triage.parse_llm_response(raw, "Se cayó la casa con 3 personas")
    assert parsed["categoria"] == "RES"
    assert parsed["prioridad"] == CRITICO
    assert parsed["necesidades"] == ["camillas", "equipo de corte"]
    assert parsed["fuente"] == "ollama"


def test_parse_llm_response_handles_unknown_category_and_priority():
    raw = json.dumps({
        "categoria": "XXX",
        "prioridad": "Media",
        "necesidades": "agua potable",
        "resumen": "Albergue sin agua",
    })
    parsed = triage.parse_llm_response(raw, "Albergue sin agua potable")
    assert parsed["categoria"] == "ALB"
    assert parsed["prioridad"] == MODERADO
    assert parsed["necesidades"] == ["agua potable"]


def test_analyze_message_falls_back_when_ollama_unreachable(monkeypatch):
    def boom(*_a, **_kw):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(triage, "query_ollama", boom)
    res = triage.analyze_message("Albergue Norte necesita agua potable")
    assert res["fuente"] == "fallback"
    assert res["categoria"] == "ALB"
    assert res["prioridad"] == MODERADO


def test_triage_service_persists_and_escalates_critical_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "triage.db"))
    conn = db.connect()
    with conn:
        db.touch_node(conn, "nodo-2", 1000)
        cur = conn.execute(
            """INSERT INTO messages (direction, from_node, text, priority, lat, lon, ts)
               VALUES ('in', 'nodo-2', ?, ?, 5.068, -75.517, 1000)""",
            ("Se cayó el techo encima de mi abuela", INFORMATIVO),
        )
        msg_id = cur.lastrowid
    conn.close()

    def fake_analyzer(_text, _node_name):
        return {
            "categoria": "RES",
            "subcategoria": "Persona bajo techo caído",
            "prioridad": CRITICO,
            "necesidades": ["rescate", "ambulancia"],
            "resumen": "Adulta mayor atrapada bajo techo",
            "fuente": "ollama",
            "modelo": "qwen2.5:1.5b",
        }

    bus = FakeBus()
    svc = triage.TriageService(bus, analyzer=fake_analyzer)
    event = svc.process_message({
        "id": msg_id,
        "direction": "in",
        "from_node": "nodo-2",
        "long_name": "Barrio Galán",
        "text": "Se cayó el techo encima de mi abuela",
        "priority": INFORMATIVO,
        "lat": 5.068,
        "lon": -75.517,
        "ts": 1000,
    })

    assert event["categoria"] == "RES"
    assert event["prioridad"] == CRITICO
    topics = [t for t, _ in bus.events]
    assert config.EV_TRIAGE in topics
    assert config.EV_ALERT in topics

    # Verifica persistencia y escalado en SQLite
    row = svc.conn.execute("SELECT * FROM triage WHERE message_id = ?", (msg_id,)).fetchone()
    assert row["categoria"] == "RES" and row["prioridad"] == CRITICO
    assert json.loads(row["necesidades"]) == ["rescate", "ambulancia"]
    msg_row = svc.conn.execute("SELECT priority FROM messages WHERE id = ?", (msg_id,)).fetchone()
    assert msg_row["priority"] == CRITICO
    alert_row = svc.conn.execute("SELECT type, node_id FROM alerts").fetchone()
    assert alert_row["type"] == "mensaje_critico" and alert_row["node_id"] == "nodo-2"
    svc.conn.close()


def test_triage_ignores_outgoing_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "triage_out.db"))
    bus = FakeBus()
    svc = triage.TriageService(bus)
    svc.on_message(config.EV_MESSAGE, {"id": 9, "direction": "out", "text": "Brigada en camino"})
    assert svc.queue.empty()
    svc.conn.close()


def test_parse_llm_response_filters_empty_needs_like_nada():
    raw = json.dumps({
        "categoria": "GEN",
        "subcategoria": "Patrullaje sin novedad",
        "prioridad": "informativo",
        "necesidades": ["nada", "ninguna", "No aplica"],
        "resumen": "Todo tranquilo",
    })
    parsed = triage.parse_llm_response(raw, "Patrullaje sin novedad")
    assert parsed["necesidades"] == []


def test_analyze_message_handles_empty_and_irrelevant_messages():
    res_empty = triage.analyze_message("   ")
    assert res_empty["categoria"] == "GEN"
    assert res_empty["prioridad"] == triage.PENDIENTE
    assert res_empty["necesidades"] == []

    for text in ("hola", "buenas tardes", "probando 1 2 3", "copiado listo"):
        res = triage.analyze_message(text)
        assert res["categoria"] == "GEN"
        assert res["prioridad"] == INFORMATIVO
        assert res["necesidades"] == []


def test_safety_floor_prevents_downgrading_critical_priority(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "safety.db"))
    conn = db.connect()
    with conn:
        db.touch_node(conn, "nodo-3", 1000)
        cur = conn.execute(
            """INSERT INTO messages (direction, from_node, text, priority, ts)
               VALUES ('in', 'nodo-3', 'SOS hay 2 personas atrapadas', ?, 1000)""",
            (CRITICO,),
        )
        msg_id = cur.lastrowid
    conn.close()

    # Simulamos que la IA erróneamente quiso responder "informativo" o "INF"
    def hallucinating_analyzer(_text, _node_name):
        return {
            "categoria": "INF",
            "subcategoria": "abandono de vía",
            "prioridad": INFORMATIVO,
            "necesidades": [],
            "resumen": "Reporte vial",
            "fuente": "ollama",
            "modelo": "qwen2.5:1.5b",
        }

    bus = FakeBus()
    svc = triage.TriageService(bus, analyzer=hallucinating_analyzer)
    event = svc.process_message({
        "id": msg_id,
        "direction": "in",
        "from_node": "nodo-3",
        "text": "SOS hay 2 personas atrapadas",
        "priority": CRITICO,
        "ts": 1000,
    })

    # El piso de seguridad debió forzar CRITICO y corregir a RES (Rescate)
    assert event["prioridad"] == CRITICO
    assert event["categoria"] == "RES"
    row = svc.conn.execute("SELECT prioridad, categoria FROM triage WHERE message_id = ?", (msg_id,)).fetchone()
    assert row["prioridad"] == CRITICO and row["categoria"] == "RES"
    svc.conn.close()
