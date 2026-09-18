/**
 * Shared leaflet helper components.
 */

import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";

/** Fit the map viewport to a set of positions (once they change). */
export function FitToPositions({
  positions,
  padding = 8,
}: {
  positions: [number, number][];
  padding?: number;
}): null {
  const map = useMap();
  useEffect(() => {
    if (positions.length < 2) return;
    map.fitBounds(L.latLngBounds(positions.map((p) => L.latLng(p[0], p[1]))), {
      padding: [padding, padding],
    });
  }, [map, positions, padding]);
  return null;
}
