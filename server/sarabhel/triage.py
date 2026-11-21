"""Worker de triaje con IA local (Ollama + qwen2.5:1.5b).

Se suscribe a `events/msg` de forma asíncrona para no bloquear la mensajería de radio:
1. Analiza cada mensaje entrante con Ollama en modo JSON estricto siguiendo el catálogo EDAN.
2. Si Ollama no responde o falla, aplica un clasificador de respaldo (fallback heurístico).
3. Guarda el resultado en la tabla `triage` y publica `events/triage` para el mapa y la app.
4. Si la IA detecta una emergencia crítica que las palabras clave pasaron por alto, escala
   la prioridad del mensaje, actualiza el nodo y emite `events/alert`.
"""
from __future__ import annotations

import json
import queue
import re
import threading
import urllib.error
import urllib.request
from typing import Any

from . import config, db
from .bus import Bus
from .priority import CRITICO, INFORMATIVO, MODERADO, classify, normalize

log = config.setup_logging("triaje")

PENDIENTE = "pendiente"

CATEGORIES = {
    "RES": "Rescate",
    "SAL": "Salud",
    "ABA": "Abastecimiento",
    "INF": "Infraestructura",
    "NAT": "Fenómenos naturales",
    "SER": "Servicios básicos",
    "ALB": "Albergues",
    "COM": "Comunicaciones",
    "PRO": "Protección",
    "AMB": "Ambiental",
    "LOG": "Logística",
    "GEN": "General",
}

PRIORITY_ALIASES = {
    "critico": CRITICO,
    "critica": CRITICO,
    "alta": CRITICO,
    "alto": CRITICO,
    "urgente": CRITICO,
    "rojo": CRITICO,
    "moderado": MODERADO,
    "moderada": MODERADO,
    "media": MODERADO,
    "medio": MODERADO,
    "amarillo": MODERADO,
    "informativo": INFORMATIVO,
    "informativa": INFORMATIVO,
    "baja": INFORMATIVO,
    "bajo": INFORMATIVO,
    "verde": INFORMATIVO,
    "pendiente": PENDIENTE,
    "duda": PENDIENTE,
    "desconocido": PENDIENTE,
    "blanco": PENDIENTE,
}

SYSTEM_PROMPT = """Eres un agente de triaje de emergencias del Puesto de Mando Unificado (PMU) en Colombia.
Analiza el mensaje recibido por radio y responde SOLO un objeto JSON válido con estas claves exactas:
{
  "categoria": "UNO DE: RES, SAL, ABA, INF, NAT, SER, ALB, COM, PRO, AMB, LOG, GEN",
  "subcategoria": "frase corta de máximo 40 caracteres",
  "prioridad": "UNO DE: critico, moderado, informativo, pendiente",
  "necesidades": ["lista de recursos específicos requeridos, o [] si no hay"],
  "resumen": "resumen operativo breve de máximo 120 caracteres"
}

Reglas estrictas de clasificación:
1. RIESGO VITAL ("critico"): personas atrapadas, sepultadas bajo techos/escombros, heridos graves, colapsos con gente dentro, asfixia, fuego activo o fuga de gas. Si hay una persona atrapada bajo un techo o pared, la categoría es RES (Rescate) o SAL (Salud), NUNCA infraestructura.
2. AFECTACIÓN SEVERA ("moderado"): falta de agua/alimentos en albergues o comunidades, vía bloqueada, desabastecimiento médico no vital, corte general de servicios.
3. INFORMATIVO / RUTINA ("informativo"): reporte de patrullaje sin novedad, situación bajo control, confirmación de bienestar.
4. MENSAJES IRRELEVANTES O PRUEBAS ("informativo" / categoria "GEN"): si el mensaje es un saludo casual ("hola", "buenos días"), prueba de radio ("probando 1 2 3", "copiado"), charla no relacionada o texto irrelevante, clasifícalo en categoria "GEN", subcategoría "Mensaje informal o de prueba", prioridad "informativo" y necesidades [].
5. AMBIGUO O INCOMPLETO ("pendiente"): si el texto está cortado, contiene solo signos o es demasiado vago para saber si hay una emergencia real ("aló?", "ayuda...", "se escuchó algo").
6. NECESIDADES: Solo lista recursos tangibles (ej. ["agua potable", "camillas"]). Si no se requieren recursos tangibles, DEBE ser exactamente una lista vacía []. NUNCA escribas ["nada"], ["ninguna"] ni ["no aplica"]."""

FEW_SHOT_EXAMPLES: list[dict[str, str]] = [
    {
        "role": "user",
        "content": "Remitente: Albergue 1\nMensaje: Se cayó el techo encima de mi abuela en el barrio Galán",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "categoria": "RES",
            "subcategoria": "Persona atrapada bajo techo",
            "prioridad": "critico",
            "necesidades": ["equipo de rescate", "ambulancia"],
            "resumen": "Adulta mayor atrapada tras colapso de techo en barrio Galán",
        }, ensure_ascii=False),
    },
    {
        "role": "user",
        "content": "Remitente: Albergue Coliseo\nMensaje: Albergue Coliseo con 180 personas sin agua potable ni cobijas",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "categoria": "ALB",
            "subcategoria": "Albergue sin agua ni abrigo",
            "prioridad": "moderado",
            "necesidades": ["agua potable", "cobijas"],
            "resumen": "Albergue Coliseo con 180 personas requiere agua potable y cobijas",
        }, ensure_ascii=False),
    },
    {
        "role": "user",
        "content": "Remitente: Brigada 3\nMensaje: Patrullaje sin novedad en la plaza, todo tranquilo",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "categoria": "GEN",
            "subcategoria": "Patrullaje sin novedad",
            "prioridad": "informativo",
            "necesidades": [],
            "resumen": "Sector plaza principal en calma sin afectaciones",
        }, ensure_ascii=False),
    },
    {
        "role": "user",
        "content": "Remitente: Nodo 4\nMensaje: hola buenas tardes probando radio 1 2 3 me copian",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "categoria": "GEN",
            "subcategoria": "Prueba de radio o saludo",
            "prioridad": "informativo",
            "necesidades": [],
            "resumen": "Mensaje de prueba técnica de radio sin reporte de emergencia",
        }, ensure_ascii=False),
    },
    {
        "role": "user",
        "content": "Remitente: Nodo 5\nMensaje: se escucho un ruido fuerte arriba...",
    },
    {
        "role": "assistant",
        "content": json.dumps({
            "categoria": "GEN",
            "subcategoria": "Reporte ambiguo sin confirmar",
            "prioridad": "pendiente",
            "necesidades": [],
            "resumen": "Ruido no identificado en parte alta; requiere confirmación en terreno",
        }, ensure_ascii=False),
    },
]

# Heurística de categorías para el modo fallback cuando Ollama no está disponible.
_FALLBACK_CATS: list[tuple[str, re.Pattern[str]]] = [
    ("RES", re.compile(r"\b(?:atrapad\w*|sepultad\w*|escombros?|rescat\w*|desaparecid\w*|sos)\b")),
    ("SAL", re.compile(r"\b(?:herid\w*|sangr\w*|fractur\w*|inconscient\w*|infarto|medicin\w*|medicament\w*|insulina|enferm\w*|no respira)\b")),
    ("NAT", re.compile(r"\b(?:sismo|terremoto|temblor|deslizamiento|derrumb\w*|inundaci\w*|incendi\w*|fuego|creciente)\b")),
    ("ALB", re.compile(r"\b(?:albergue\w*|refugio\w*|ocupacion|cobijas?)\b")),
    ("ABA", re.compile(r"\b(?:agua|comida|aliment\w*|viveres|racion\w*)\b")),
    ("INF", re.compile(r"\b(?:via|carretera|puente|bloquead\w*|grietas?|colaps\w*|vivienda|casa|techo)\b")),
    ("SER", re.compile(r"\b(?:luz|electric\w*|energia|gas|acueducto|alcantarillado)\b")),
    ("COM", re.compile(r"\b(?:incomunicad\w*|sin senal|radio|bateria\w*)\b")),
    ("PRO", re.compile(r"\b(?:evacu\w*|ninos?|bebes?|embarazada|anciano\w*)\b")),
]

_IRRELEVANT_PATTERNS = re.compile(
    r"^(?:hola|buen[oa]s? (?:dias|tardes|noches)|probando(?:\s*(?:1\s*2\s*3|radio))?|prueba|test|copiado|recibido|ok|listo|que tal|como estan)[\s.!,?]*$",
    re.I,
)

_EMPTY_NEEDS = {
    "nada", "ninguna", "ninguno", "ningun", "ningunas", "ningunos",
    "no", "no aplica", "n/a", "na", "sin necesidades", "nadie",
    "ningun recurso", "ninguna necesidad", "ninguno por ahora",
}


def _normalize_priority(raw: Any, fallback_text: str) -> str:
    if isinstance(raw, str):
        key = normalize(raw).strip()
        if key in PRIORITY_ALIASES:
            return PRIORITY_ALIASES[key]
    return classify(fallback_text)


def _normalize_category(raw: Any, fallback_text: str) -> str:
    if isinstance(raw, str):
        code = raw.strip().upper()[:3]
        if code in CATEGORIES:
            return code
    return fallback_category(fallback_text)


def fallback_category(text: str) -> str:
    t = normalize(text)
    for code, pattern in _FALLBACK_CATS:
        if pattern.search(t):
            return code
    return "GEN"


def fallback_triage(text: str) -> dict[str, Any]:
    """Clasificación determinista sin LLM cuando Ollama está apagado o lento."""
    clean = text.strip()
    if not clean:
        return {
            "categoria": "GEN",
            "subcategoria": "Mensaje vacío",
            "prioridad": PENDIENTE,
            "necesidades": [],
            "resumen": "Mensaje recibido sin contenido de texto",
            "fuente": "fallback",
            "modelo": None,
        }
    if _IRRELEVANT_PATTERNS.match(clean):
        return {
            "categoria": "GEN",
            "subcategoria": "Mensaje informal o de prueba",
            "prioridad": INFORMATIVO,
            "necesidades": [],
            "resumen": "Mensaje informal o prueba técnica sin reporte de emergencia",
            "fuente": "fallback",
            "modelo": None,
        }
    prio = classify(clean)
    cat = fallback_category(clean)
    if prio == INFORMATIVO and len(clean) < 8:
        prio = PENDIENTE
    return {
        "categoria": cat,
        "subcategoria": CATEGORIES[cat],
        "prioridad": prio,
        "necesidades": [],
        "resumen": clean[:120],
        "fuente": "fallback",
        "modelo": None,
    }


def parse_llm_response(raw_content: str, original_text: str) -> dict[str, Any]:
    """Valida y normaliza la respuesta JSON devuelta por Ollama."""
    body = raw_content.strip()
    if body.startswith("```"):
        body = re.sub(r"^```(?:json)?\s*|\s*```$", "", body, flags=re.I | re.S).strip()
    data = json.loads(body)
    if not isinstance(data, dict):
        raise ValueError("La respuesta de Ollama no es un objeto JSON")

    categoria = _normalize_category(data.get("categoria"), original_text)
    prioridad = _normalize_priority(data.get("prioridad"), original_text)
    sub = str(data.get("subcategoria") or CATEGORIES[categoria]).strip()[:40]
    resumen = str(data.get("resumen") or original_text).strip()[:120]

    raw_needs = data.get("necesidades")
    necesidades: list[str] = []
    if isinstance(raw_needs, list):
        for item in raw_needs:
            val = str(item).strip()[:40]
            if val and normalize(val) not in _EMPTY_NEEDS and val.lower() not in _EMPTY_NEEDS:
                necesidades.append(val)
        necesidades = necesidades[:6]
    elif isinstance(raw_needs, str) and raw_needs.strip():
        val = raw_needs.strip()[:40]
        if val and normalize(val) not in _EMPTY_NEEDS and val.lower() not in _EMPTY_NEEDS:
            necesidades = [val]

    return {
        "categoria": categoria,
        "subcategoria": sub,
        "prioridad": prioridad,
        "necesidades": necesidades,
        "resumen": resumen,
        "fuente": "ollama",
        "modelo": config.OLLAMA_MODEL,
    }


def query_ollama(text: str, node_name: str | None = None) -> dict[str, Any]:
    """Llama a la API REST local de Ollama (/api/chat) con prompt few-shot y JSON estricto."""
    user_msg = f"Remitente: {node_name or 'Desconocido'}\nMensaje: {text}"
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(FEW_SHOT_EXAMPLES)
    messages.append({"role": "user", "content": user_msg})

    payload = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": 180},
        "messages": messages,
    }
    req = urllib.request.Request(
        f"{config.OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=config.OLLAMA_TIMEOUT_SECS) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = ((body.get("message") or {}).get("content")) or ""
    if not content:
        raise ValueError("Respuesta vacía de Ollama")
    return parse_llm_response(content, text)


def analyze_message(text: str, node_name: str | None = None) -> dict[str, Any]:
    """Ejecuta triaje con Ollama y conmuta a fallback si ocurre cualquier error."""
    clean = (text or "").strip()
    if not clean or _IRRELEVANT_PATTERNS.match(clean):
        return fallback_triage(clean)
    if not config.TRIAGE_ENABLED:
        return fallback_triage(clean)
    try:
        return query_ollama(clean, node_name)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        log.warning("Ollama no disponible o respuesta inválida (%s); usando fallback", exc)
        return fallback_triage(clean)


class TriageService:
    def __init__(self, bus: Bus, analyzer=analyze_message):
        self.bus = bus
        self.analyzer = analyzer
        self.conn = db.connect()
        self.lock = threading.Lock()
        self.queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=200)

    def on_message(self, _topic: str, payload: dict[str, Any]) -> None:
        if payload.get("direction") != "in":
            return
        if not payload.get("id") or not str(payload.get("text", "")).strip():
            return
        try:
            self.queue.put_nowait(payload)
        except queue.Full:
            log.warning("Cola de triaje llena; descartando mensaje %s", payload.get("id"))

    def process_message(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        msg_id = int(payload["id"])
        text = str(payload.get("text", "")).strip()
        node = payload.get("from_node")
        long_name = payload.get("long_name")
        lat, lon = payload.get("lat"), payload.get("lon")
        ts = int(payload.get("ts") or db.now())
        prev_priority = payload.get("priority")

        result = self.analyzer(text, long_name or node)

        # Piso de seguridad: si el clasificador heurístico ya marcó el mensaje como CRITICO
        # (por ejemplo: SOS, atrapados, herido grave, derrumbe), la IA JAMÁS puede degradar la prioridad.
        if prev_priority == CRITICO and result.get("prioridad") != CRITICO:
            log.warning("Piso de seguridad activado: msg=%s era CRITICO pero IA sugirió %s. Manteniendo CRITICO.",
                        msg_id, result.get("prioridad"))
            result["prioridad"] = CRITICO
            if result.get("categoria") in ("INF", "GEN"):
                result["categoria"] = "RES"
                result["subcategoria"] = "Rescate en estructura colapsada"

        needs_json = json.dumps(result["necesidades"], ensure_ascii=False)
        escalated_alert = None

        with self.lock, self.conn:
            self.conn.execute(
                """INSERT INTO triage (message_id, node_id, categoria, subcategoria, prioridad,
                                       necesidades, resumen, modelo, fuente, lat, lon, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(message_id) DO UPDATE SET
                     categoria = excluded.categoria,
                     subcategoria = excluded.subcategoria,
                     prioridad = excluded.prioridad,
                     necesidades = excluded.necesidades,
                     resumen = excluded.resumen,
                     modelo = excluded.modelo,
                     fuente = excluded.fuente,
                     ts = excluded.ts""",
                (msg_id, node, result["categoria"], result["subcategoria"], result["prioridad"],
                 needs_json, result["resumen"], result["modelo"], result["fuente"], lat, lon, ts),
            )
            # Si las palabras clave no lo marcaron crítico pero la IA sí, escalamos prioridad y alerta.
            if result["prioridad"] == CRITICO and prev_priority != CRITICO:
                self.conn.execute("UPDATE messages SET priority = ? WHERE id = ?", (CRITICO, msg_id))
                if node:
                    self.conn.execute("UPDATE nodes SET alert_ts = ? WHERE node_id = ?", (ts, node))
                escalated_alert = db.create_alert(self.conn, {
                    "type": "mensaje_critico",
                    "node_id": node,
                    "long_name": long_name,
                    "text": f"[{result['categoria']}] {text}",
                    "lat": lat,
                    "lon": lon,
                    "ts": ts,
                })

        event = {
            "message_id": msg_id,
            "node_id": node,
            "long_name": long_name,
            "text": text,
            "categoria": result["categoria"],
            "categoria_nombre": CATEGORIES.get(result["categoria"], "General"),
            "subcategoria": result["subcategoria"],
            "prioridad": result["prioridad"],
            "necesidades": result["necesidades"],
            "resumen": result["resumen"],
            "modelo": result["modelo"],
            "fuente": result["fuente"],
            "lat": lat,
            "lon": lon,
            "ts": ts,
        }
        self.bus.publish(config.EV_TRIAGE, event)
        if escalated_alert:
            self.bus.publish(config.EV_ALERT, escalated_alert)
        log.info("Triaje msg=%s [%s/%s] (%s): %s",
                 msg_id, result["categoria"], result["prioridad"], result["fuente"], result["resumen"])
        return event

    def worker_loop(self) -> None:
        while True:
            payload = self.queue.get()
            try:
                self.process_message(payload)
            except Exception:
                log.exception("Error ejecutando triaje para mensaje %r", payload.get("id"))
            finally:
                self.queue.task_done()


def main() -> None:
    bus = Bus("triaje")
    svc = TriageService(bus)
    threading.Thread(target=svc.worker_loop, daemon=True, name="triage-worker").start()
    bus.subscribe(config.EV_MESSAGE, svc.on_message)
    log.info("Worker de triaje iniciado (modelo=%s, url=%s, habilitado=%s)",
             config.OLLAMA_MODEL, config.OLLAMA_URL, config.TRIAGE_ENABLED)
    bus.run_forever()


if __name__ == "__main__":
    main()
