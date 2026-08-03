import { useEffect, useRef } from "react";
import { MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import type { LatLngBounds } from "leaflet";
import L from "leaflet";
import type { GeoJSONFeatureCollection } from "../api";

// Component to fit map bounds to polyline
function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  const hasFitted = useRef(false);
  
  useEffect(() => {
    if (positions.length > 0 && !hasFitted.current) {
      const bounds: LatLngBounds = L.latLngBounds(positions.map(p => L.latLng(p[0], p[1])));
      map.fitBounds(bounds, { padding: [10, 10] });
      hasFitted.current = true;
    }
  }, [map, positions]);
  
  return null;
}

interface MiniMapProps {
  geojson: GeoJSONFeatureCollection | null;
  className?: string;
}

export function MiniMap({ geojson, className = "" }: MiniMapProps) {
  // Extract positions from GeoJSON
  const positions: [number, number][] = geojson
    ? geojson.features
        .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
        .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number])
    : [];

  if (positions.length < 2) {
    return (
      <div className={`bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center ${className}`}>
        <span className="text-xs text-gray-400">No GPS data</span>
      </div>
    );
  }

  // Calculate center for initial view
  const center: [number, number] = [
    positions.reduce((sum, p) => sum + p[0], 0) / positions.length,
    positions.reduce((sum, p) => sum + p[1], 0) / positions.length,
  ];

  return (
    <div className={`rounded-lg overflow-hidden ${className}`}>
      <MapContainer
        center={center}
        zoom={12}
        scrollWheelZoom={false}
        dragging={false}
        zoomControl={false}
        attributionControl={false}
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Polyline positions={positions} color="#6366f1" weight={3} />
        <FitBounds positions={positions} />
      </MapContainer>
    </div>
  );
}
