"""Zonas de riesgo (GeoJSON) y prueba punto-en-polígono sin dependencias."""
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def load_zones(path: str) -> list[dict]:
    """Devuelve [{name, rings: [[(lon, lat), ...], ...]}] por cada polígono."""
    p = Path(path)
    if not p.exists():
        log.warning("Archivo de zonas %s no existe; sin geocercas", path)
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    zones = []
    for feat in data.get("features", []):
        geom = feat.get("geometry") or {}
        name = (feat.get("properties") or {}).get("name", "Zona sin nombre")
        if geom.get("type") == "Polygon":
            polys = [geom["coordinates"]]
        elif geom.get("type") == "MultiPolygon":
            polys = geom["coordinates"]
        else:
            continue
        for rings in polys:
            zones.append({"name": name, "rings": [[tuple(pt[:2]) for pt in ring] for ring in rings]})
    log.info("Cargadas %d zonas de riesgo", len(zones))
    return zones


def _in_ring(lon: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def find_zone(zones: list[dict], lat: float, lon: float) -> str | None:
    for z in zones:
        outer, *holes = z["rings"]
        if _in_ring(lon, lat, outer) and not any(_in_ring(lon, lat, h) for h in holes):
            return z["name"]
    return None


def valid_coords(lat, lon) -> bool:
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)
