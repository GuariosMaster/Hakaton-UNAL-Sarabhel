"""Clasificación de prioridad de mensajes por palabras clave (español).

Es deliberadamente simple y explicable: el operador ve por qué se marcó algo
como crítico. Ajustar las listas con el equipo de gestión del riesgo.
"""
import re
import unicodedata

CRITICO = "critico"
MODERADO = "moderado"
INFORMATIVO = "informativo"

_CRITICAL = [
    r"sos", r"auxilio", r"socorro", r"emergencia", r"urgente",
    r"herid\w*", r"atrapad\w*", r"sangr\w*", r"fractur\w*", r"inconscient\w*",
    r"no respira", r"infarto", r"incendi\w*", r"fuego", r"explosi\w*",
    r"derrumb\w*", r"colaps\w*", r"escombros?", r"sepultad\w*", r"deslizamiento",
    r"(fuga|olor) a gas", r"muert[oa]s?", r"desaparecid\w*",
]
_MODERATE = [
    r"agua", r"comida", r"aliment\w*", r"medicina\w*", r"medicament\w*", r"insulina",
    r"refugio", r"albergue", r"evacu\w*", r"grietas?", r"cobijas?", r"frio",
    r"bateria\w*", r"bebes?", r"embarazada", r"ayuda", r"necesit\w*", r"bloquead\w*",
]


def _compile(words: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(words) + r")\b")


_RE_CRITICAL = _compile(_CRITICAL)
_RE_MODERATE = _compile(_MODERATE)


def normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def classify(text: str) -> str:
    t = normalize(text)
    if _RE_CRITICAL.search(t):
        return CRITICO
    if _RE_MODERATE.search(t):
        return MODERADO
    return INFORMATIVO
