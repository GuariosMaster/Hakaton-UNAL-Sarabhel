"""Usuarios, PIN de 4 dígitos, sesiones y roles.

Roles:
  admin       todo, incluida la administración de usuarios
  mando       puesto de mando: ver todo, gestionar alertas, enviar mensajes, exportar
  socorrista  campo: enviar reportes/SOS por Wi-Fi, ver la red y atender las alertas de su equipo

Un PIN de 4 dígitos tiene solo 10.000 combinaciones, así que se protege con:
  - PBKDF2-SHA256 con sal por usuario (no se guarda el PIN),
  - bloqueo temporal tras 5 intentos fallidos,
  - sesiones con vencimiento (12 h) que se pueden cerrar.
"""
import hashlib
import hmac
import logging
import re
import secrets
import sqlite3
import threading
import time

from . import config, db

log = logging.getLogger(__name__)

ROLES = ("admin", "mando", "socorrista")
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,20}$")
PIN_RE = re.compile(r"^\d{4}$")
SESSION_SECS = 12 * 3600
MAX_FAILS = 5
LOCK_SECS = 5 * 60
PBKDF2_ROUNDS = 120_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    usuario     TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    rol         TEXT NOT NULL CHECK (rol IN ('admin', 'mando', 'socorrista')),
    equipo      TEXT,                -- equipo de rescate (para las alertas asignadas)
    salt        TEXT NOT NULL,
    pin_hash    TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1,
    pin_inicial INTEGER NOT NULL DEFAULT 0,  -- 1 = debe cambiar el PIN que le asignaron
    creado_ts   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token     TEXT PRIMARY KEY,
    usuario   TEXT NOT NULL REFERENCES users(usuario) ON DELETE CASCADE,
    expira    INTEGER NOT NULL
);
"""


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def hash_pin(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()


def public(row: sqlite3.Row | dict) -> dict:
    r = dict(row)
    return {k: r[k] for k in ("usuario", "nombre", "rol", "equipo", "activo", "pin_inicial") if k in r}


class Auth:
    def __init__(self):
        self.lock = threading.Lock()
        self.fails: dict[str, tuple[int, float]] = {}  # usuario -> (intentos, hasta)
        conn = self._conn()
        try:
            conn.executescript(SCHEMA)
            if not conn.execute("SELECT 1 FROM users WHERE rol = 'admin' AND activo = 1").fetchone():
                self._insert(conn, "admin", "Administrador", "admin", None, config.ADMIN_PIN, inicial=True)
                log.warning("Creado el usuario 'admin' con el PIN inicial %s: cámbialo al entrar.",
                            "de ADMIN_PIN" if config.ADMIN_PIN != "1234" else "1234")
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _conn() -> sqlite3.Connection:
        conn = db.connect()
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _insert(conn, usuario, nombre, rol, equipo, pin, inicial):
        salt = secrets.token_hex(16)
        conn.execute(
            """INSERT INTO users (usuario, nombre, rol, equipo, salt, pin_hash, pin_inicial, creado_ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (usuario, nombre, rol, equipo, salt, hash_pin(pin, salt), int(inicial), db.now()))

    # --- sesiones ---------------------------------------------------------------
    def login(self, usuario: str, pin: str) -> dict:
        usuario = (usuario or "").strip().lower()
        with self.lock:
            n, hasta = self.fails.get(usuario, (0, 0.0))
            if hasta > time.time():
                raise AuthError(429, f"Demasiados intentos. Espera {int(hasta - time.time()) // 60 + 1} min.")
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE usuario = ? AND activo = 1", (usuario,)).fetchone()
            ok = bool(row) and PIN_RE.match(pin or "") and hmac.compare_digest(
                hash_pin(pin, row["salt"]), row["pin_hash"])
            if not ok:
                with self.lock:
                    n, _ = self.fails.get(usuario, (0, 0.0))
                    n += 1
                    self.fails[usuario] = (0, time.time() + LOCK_SECS) if n >= MAX_FAILS else (n, 0.0)
                left = MAX_FAILS - n
                raise AuthError(401, "Usuario o PIN incorrecto" +
                                (f". Te quedan {left} intento{'s' if left != 1 else ''}." if left > 0 else
                                 ". Cuenta bloqueada 5 minutos."))
            with self.lock:
                self.fails.pop(usuario, None)
            token = secrets.token_urlsafe(24)
            expira = db.now() + SESSION_SECS
            with conn:
                conn.execute("DELETE FROM sessions WHERE expira < ?", (db.now(),))
                conn.execute("INSERT INTO sessions (token, usuario, expira) VALUES (?, ?, ?)", (token, usuario, expira))
            return {"token": token, "expira": expira, **public(row)}
        finally:
            conn.close()

    def session(self, token: str | None) -> dict:
        if not token:
            raise AuthError(401, "Inicia sesión")
        conn = self._conn()
        try:
            row = conn.execute(
                """SELECT u.* FROM sessions s JOIN users u ON u.usuario = s.usuario
                   WHERE s.token = ? AND s.expira > ? AND u.activo = 1""", (token, db.now())).fetchone()
        finally:
            conn.close()
        if not row:
            raise AuthError(401, "La sesión venció; vuelve a entrar")
        return public(row)

    def logout(self, token: str) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        finally:
            conn.close()

    # --- usuarios (solo admin) ------------------------------------------------
    def list_users(self) -> list[dict]:
        conn = self._conn()
        try:
            return [public(r) for r in conn.execute("SELECT * FROM users ORDER BY rol, usuario")]
        finally:
            conn.close()

    def create_user(self, usuario: str, nombre: str, rol: str, pin: str, equipo: str | None) -> dict:
        usuario = usuario.strip().lower()
        self._validate(usuario=usuario, rol=rol, pin=pin)
        conn = self._conn()
        try:
            with conn:
                try:
                    self._insert(conn, usuario, nombre.strip(), rol, (equipo or "").strip() or None, pin, inicial=True)
                except sqlite3.IntegrityError:
                    raise AuthError(409, f"El usuario '{usuario}' ya existe")
            return public(conn.execute("SELECT * FROM users WHERE usuario = ?", (usuario,)).fetchone())
        finally:
            conn.close()

    def update_user(self, usuario: str, *, by: str, nombre=None, rol=None, equipo=None, activo=None,
                    pin=None) -> dict:
        self._validate(rol=rol, pin=pin)
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE usuario = ?", (usuario,)).fetchone()
            if not row:
                raise AuthError(404, "Usuario no encontrado")
            if usuario == by and (activo is False or (rol and rol != "admin")):
                raise AuthError(400, "No puedes desactivarte ni quitarte el rol de administrador")
            sets, vals = [], []
            for col, val in (("nombre", nombre), ("rol", rol), ("equipo", equipo)):
                if val is not None:
                    sets.append(f"{col} = ?")
                    vals.append((val.strip() or None) if col == "equipo" else val.strip())
            if activo is not None:
                sets.append("activo = ?")
                vals.append(int(activo))
            if pin is not None:
                salt = secrets.token_hex(16)
                sets += ["salt = ?", "pin_hash = ?", "pin_inicial = ?"]
                vals += [salt, hash_pin(pin, salt), int(usuario != by)]  # PIN puesto por otro: debe cambiarlo
            if sets:
                with conn:
                    conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE usuario = ?", (*vals, usuario))
                    if activo is False or pin is not None and usuario != by:
                        conn.execute("DELETE FROM sessions WHERE usuario = ?", (usuario,))
            return public(conn.execute("SELECT * FROM users WHERE usuario = ?", (usuario,)).fetchone())
        finally:
            conn.close()

    def delete_user(self, usuario: str, *, by: str) -> None:
        if usuario == by:
            raise AuthError(400, "No puedes eliminar tu propio usuario")
        conn = self._conn()
        try:
            with conn:
                if conn.execute("DELETE FROM users WHERE usuario = ?", (usuario,)).rowcount == 0:
                    raise AuthError(404, "Usuario no encontrado")
        finally:
            conn.close()

    # --- registro propio ------------------------------------------------------
    def register(self, usuario: str, nombre: str, pin: str, equipo: str | None) -> dict:
        """Cualquier persona crea su cuenta y entra de una vez. Siempre como socorrista: los
        roles de puesto de mando y administrador solo los da un administrador."""
        if not config.REGISTRATION_OPEN:
            raise AuthError(403, "El registro está cerrado: pide una cuenta al administrador")
        usuario = (usuario or "").strip().lower()
        self._validate(usuario=usuario, pin=pin)
        self._check_strong(pin)
        if not (nombre or "").strip():
            raise AuthError(400, "Escribe tu nombre")
        conn = self._conn()
        try:
            with conn:
                try:
                    self._insert(conn, usuario, nombre.strip(), "socorrista", (equipo or "").strip() or None,
                                 pin, inicial=False)
                except sqlite3.IntegrityError:
                    raise AuthError(409, f"El usuario '{usuario}' ya existe; elige otro o entra con tu PIN")
        finally:
            conn.close()
        log.info("Cuenta nueva registrada: %s", usuario)
        return self.login(usuario, pin)

    def status(self) -> dict:
        """Lo que la pantalla de entrada necesita saber antes de iniciar sesión."""
        conn = self._conn()
        try:
            admin = conn.execute("SELECT pin_inicial FROM users WHERE usuario = 'admin' AND activo = 1").fetchone()
        finally:
            conn.close()
        return {"registro": config.REGISTRATION_OPEN, "admin_inicial": bool(admin and admin["pin_inicial"])}

    @staticmethod
    def _check_strong(pin: str) -> None:
        if pin in ("0000", "1234", "1111", "4321", "1212") or len(set(pin)) == 1:
            raise AuthError(400, "Elige un PIN menos obvio (no 0000, 1234, 1111…)")

    def change_own_pin(self, usuario: str, actual: str, nuevo: str) -> None:
        self._validate(pin=nuevo)
        self._check_strong(nuevo)
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE usuario = ?", (usuario,)).fetchone()
            if not row or not hmac.compare_digest(hash_pin(actual, row["salt"]), row["pin_hash"]):
                raise AuthError(401, "El PIN actual no es correcto")
            salt = secrets.token_hex(16)
            with conn:
                conn.execute("UPDATE users SET salt = ?, pin_hash = ?, pin_inicial = 0 WHERE usuario = ?",
                             (salt, hash_pin(nuevo, salt), usuario))
        finally:
            conn.close()

    @staticmethod
    def _validate(usuario=None, rol=None, pin=None):
        if usuario is not None and not USERNAME_RE.match(usuario):
            raise AuthError(400, "El usuario debe tener 3-20 caracteres: letras minúsculas, números, punto o guion")
        if rol is not None and rol not in ROLES:
            raise AuthError(400, f"Rol inválido (usa {', '.join(ROLES)})")
        if pin is not None and not PIN_RE.match(pin):
            raise AuthError(400, "El PIN debe tener exactamente 4 dígitos")
