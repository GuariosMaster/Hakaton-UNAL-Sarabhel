import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";

export interface MapMarker {
  id: string;
  lat: number;
  lon: number;
  color: string;
  label: string;
  popup: string[];
  big?: boolean;
}

interface Props {
  markers: MapMarker[];
  tileUrl?: string;
  zones?: GeoJSON.FeatureCollection;
  focus?: { lat: number; lon: number; seq: number };
}

const MANIZALES: [number, number] = [5.0689, -75.5174];
const OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export function MapView({ markers, tileUrl, zones, focus }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const zoneLayer = useRef<L.GeoJSON | null>(null);
  const fitted = useRef(false);

  // Crear el mapa una sola vez.
  useEffect(() => {
    if (!box.current) return;
    const m = L.map(box.current, { zoomControl: true, attributionControl: true }).setView(MANIZALES, 13);
    L.tileLayer(tileUrl || OSM, { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(m);
    layer.current = L.layerGroup().addTo(m);
    map.current = m;
    // El contenedor puede cambiar de tamaño al cambiar de pestaña.
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(box.current);
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
    };
  }, [tileUrl]);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    zoneLayer.current?.remove();
    if (zones) {
      zoneLayer.current = L.geoJSON(zones, {
        style: { color: "#d9480f", weight: 2, fillOpacity: 0.12, dashArray: "4 4" },
        onEachFeature: (f, l) => l.bindTooltip(String(f.properties?.name ?? "Zona de riesgo")),
      }).addTo(m);
    }
  }, [zones, tileUrl]);

  useEffect(() => {
    const g = layer.current;
    const m = map.current;
    if (!g || !m) return;
    g.clearLayers();
    for (const mk of markers) {
      const c = L.circleMarker([mk.lat, mk.lon], {
        radius: mk.big ? 11 : 8, weight: 2, color: mk.color, fillColor: mk.color, fillOpacity: 0.85,
      });
      c.bindTooltip(mk.label, { permanent: true, direction: "right", offset: [8, 0], className: "map-label" });
      const pop = document.createElement("div");
      mk.popup.forEach((line, i) => {
        const el = document.createElement(i === 0 ? "b" : "div");
        el.textContent = line;
        pop.append(el);
      });
      c.bindPopup(pop);
      c.addTo(g);
    }
    if (!fitted.current && markers.length > 0) {
      fitted.current = true;
      m.fitBounds(L.latLngBounds(markers.map((x) => [x.lat, x.lon])), { padding: [40, 40], maxZoom: 15 });
    }
  }, [markers]);

  useEffect(() => {
    if (focus && map.current) map.current.flyTo([focus.lat, focus.lon], 17);
  }, [focus]);

  return <div ref={box} className="map" />;
}
