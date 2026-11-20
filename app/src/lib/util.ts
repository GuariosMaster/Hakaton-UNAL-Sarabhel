import { Geolocation } from "@capacitor/geolocation";

export const now = () => Math.floor(Date.now() / 1000);

export function ago(ts?: number | null): string {
  if (!ts) return "nunca";
  const s = Math.max(0, now() - ts);
  if (s < 60) return `hace ${s} s`;
  if (s < 3600) return `hace ${Math.round(s / 60)} min`;
  if (s < 86400) return `hace ${Math.round(s / 3600)} h`;
  return new Date(ts * 1000).toLocaleString("es-CO");
}

export const utf8Bytes = (t: string) => new TextEncoder().encode(t).length;

export const MAX_TEXT_BYTES = 200;

export interface Fix {
  lat: number;
  lon: number;
  alt?: number;
  accuracy: number;
  ts: number;
}

/** Ubicación GPS del teléfono (permiso nativo en Android, navegador en web). */
export async function getFix(): Promise<Fix> {
  const p = await Geolocation.getCurrentPosition({ enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 });
  return {
    lat: p.coords.latitude,
    lon: p.coords.longitude,
    alt: p.coords.altitude ?? undefined,
    accuracy: p.coords.accuracy,
    ts: now(),
  };
}

/** Coordenadas al final del texto: el servidor las lee aunque el nodo no tenga GPS. */
export const withCoords = (text: string, fix?: Fix) =>
  fix ? `${text} 📍${fix.lat.toFixed(5)},${fix.lon.toFixed(5)}` : text;

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch { /* almacenamiento no disponible */ }
}
