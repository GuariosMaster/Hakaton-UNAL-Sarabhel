import { MapView, type MapMarker } from "../../components/MapView";
import { ago, now } from "../../lib/util";
import { useField } from "../../store/field";

const STALE_S = 30 * 60;

export function FieldMapScreen() {
  const { nodes, myNum, fix } = useField();

  const markers: MapMarker[] = Object.values(nodes)
    .filter((n) => n.lat != null && n.lon != null && n.num !== myNum)
    .map((n) => ({
      id: n.id,
      lat: n.lat!,
      lon: n.lon!,
      color: n.lastHeard && now() - n.lastHeard < STALE_S ? "#2f9e44" : "#9aa0a6",
      label: n.shortName ?? n.longName?.slice(0, 18) ?? n.id,
      popup: [n.longName ?? n.id, `Escuchado ${ago(n.lastHeard)}`, n.battery != null ? `Batería ${n.battery}%` : ""]
        .filter(Boolean),
    }));

  const me = myNum != null ? nodes[myNum] : undefined;
  const myLat = fix?.lat ?? me?.lat;
  const myLon = fix?.lon ?? me?.lon;
  if (myLat != null && myLon != null) {
    markers.push({ id: "yo", lat: myLat, lon: myLon, color: "#2563eb", label: "YO", big: true,
                   popup: ["Mi ubicación", fix ? `±${Math.round(fix.accuracy)} m` : "Según mi nodo"] });
  }

  return (
    <div className="screen map-screen">
      <MapView markers={markers} />
    </div>
  );
}
