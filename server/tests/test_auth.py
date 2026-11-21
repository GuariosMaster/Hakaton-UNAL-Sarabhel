"""Inicio de sesión con PIN, bloqueo por intentos y permisos por rol."""
import pytest
from fastapi.testclient import TestClient

from sarabhel import config, dashboard, db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "prueba.db"))
    monkeypatch.setattr(dashboard, "_auth", None)
    db.connect().close()
    dashboard.get_auth()
    return TestClient(dashboard.app)


def entrar(c, usuario, pin):
    r = c.post("/api/auth/login", json={"usuario": usuario, "pin": pin})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_admin_inicial_y_pin_incorrecto(client):
    r = client.post("/api/auth/login", json={"usuario": "admin", "pin": "1234"})
    assert r.status_code == 200 and r.json()["rol"] == "admin" and r.json()["pin_inicial"] == 1
    r = client.post("/api/auth/login", json={"usuario": "admin", "pin": "9999"})
    assert r.status_code == 401 and "4 intentos" in r.json()["detail"]
    assert client.post("/api/auth/login", json={"usuario": "admin", "pin": "12a4"}).status_code == 422


def test_bloqueo_tras_5_intentos(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"usuario": "admin", "pin": "0000"})
    r = client.post("/api/auth/login", json={"usuario": "admin", "pin": "1234"})
    assert r.status_code == 429  # bloqueado aunque ahora el PIN sea correcto


def test_sin_sesion_no_hay_datos(client):
    assert client.get("/api/nodes").status_code == 401
    assert client.get("/api/config").status_code == 200  # público (lo usa la pantalla de login)


def test_roles(client):
    admin = entrar(client, "admin", "1234")
    for u, rol, equipo in (("ana", "socorrista", "Bomberos 2"), ("luis", "mando", None)):
        r = client.post("/api/users", headers=admin,
                        json={"usuario": u, "nombre": u.title(), "rol": rol, "pin": "4821", "equipo": equipo})
        assert r.status_code == 201, r.text
    assert client.post("/api/users", headers=admin,
                       json={"usuario": "ana", "nombre": "x", "rol": "mando", "pin": "1111"}).status_code == 409

    ana, luis = entrar(client, "ana", "4821"), entrar(client, "luis", "4821")
    assert client.get("/api/nodes", headers=ana).status_code == 200
    assert client.get("/api/users", headers=ana).status_code == 403          # solo admin
    assert client.get("/api/users", headers=luis).status_code == 403
    assert client.get("/api/export/alertas.csv", headers=ana).status_code == 403
    assert client.get(f"/api/export/alertas.csv?token={luis['Authorization'][7:]}").status_code == 200

    # Alertas: el socorrista solo atiende las de su equipo
    conn = db.connect()
    with conn:
        mia = db.create_alert(conn, {"type": "mensaje_critico", "node_id": "nodo-2", "text": "SOS"})["id"]
        otra = db.create_alert(conn, {"type": "mensaje_critico", "node_id": "nodo-3", "text": "SOS"})["id"]
    conn.close()
    assert client.patch(f"/api/alerts/{mia}", headers=luis, json={"equipo": "Bomberos 2"}).status_code == 200
    assert client.patch(f"/api/alerts/{mia}", headers=ana, json={"estado": "atendida"}).status_code == 200
    assert client.patch(f"/api/alerts/{otra}", headers=ana, json={"estado": "atendida"}).status_code == 403
    assert client.patch(f"/api/alerts/{mia}", headers=ana, json={"equipo": "Otro"}).status_code == 403


def test_cambiar_pin_y_desactivar(client):
    admin = entrar(client, "admin", "1234")
    assert client.post("/api/auth/pin", headers=admin, json={"actual": "1234", "nuevo": "0000"}).status_code == 400
    assert client.post("/api/auth/pin", headers=admin, json={"actual": "1234", "nuevo": "5827"}).status_code == 200
    admin = entrar(client, "admin", "5827")
    client.post("/api/users", headers=admin, json={"usuario": "pepe", "nombre": "Pepe", "rol": "mando", "pin": "3333"})
    pepe = entrar(client, "pepe", "3333")
    assert client.patch("/api/users/pepe", headers=admin, json={"activo": False}).status_code == 200
    assert client.get("/api/auth/me", headers=pepe).status_code == 401      # su sesión se cerró
    assert client.patch("/api/users/admin", headers=admin, json={"activo": False}).status_code == 400
    assert client.delete("/api/users/admin", headers=admin).status_code == 400


def test_registro_propio(client):
    assert client.get("/api/auth/estado").json() == {"registro": True, "admin_inicial": True}
    r = client.post("/api/auth/registro", json={"usuario": "Maria.G", "nombre": "María", "pin": "7350",
                                                "equipo": "Cruz Roja 1"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["usuario"] == "maria.g" and d["rol"] == "socorrista" and d["token"] and d["pin_inicial"] == 0
    # Ya puede entrar y usar la red, pero no administrar
    h = {"Authorization": f"Bearer {d['token']}"}
    assert client.get("/api/nodes", headers=h).status_code == 200
    assert client.get("/api/users", headers=h).status_code == 403
    # Usuario repetido, PIN obvio y usuario inválido
    assert client.post("/api/auth/registro", json={"usuario": "maria.g", "nombre": "x", "pin": "7351"}).status_code == 409
    assert client.post("/api/auth/registro", json={"usuario": "pepe", "nombre": "x", "pin": "1234"}).status_code == 400
    assert client.post("/api/auth/registro", json={"usuario": "pe pe", "nombre": "x", "pin": "7351"}).status_code == 400


def test_registro_cerrado(client, monkeypatch):
    monkeypatch.setattr(config, "REGISTRATION_OPEN", False)
    r = client.post("/api/auth/registro", json={"usuario": "pepe", "nombre": "Pepe", "pin": "7351"})
    assert r.status_code == 403
