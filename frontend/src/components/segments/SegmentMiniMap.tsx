/**
 * Small non-interactive map that renders a single encoded polyline,
 * fitting bounds to the path. Used by the suggestions page and the
 * activity-detail inline suggestion card.
 */

import { useMemo } from "react";
import type { JSX } from "react";
import { MapContainer, Polyline, TileLayer } from "react-leaflet";
import { decodePolyline } from "@/components/PolylineMap";
import { useTileConfig } from "@/hooks/useTileUrl";
import { FitToPositions } from "@/components/segments/FitToPositions";

interface SegmentMiniMapProps {
  polyline: string;
  className?: string;
  height?: number;
}

export function SegmentMiniMap({
  polyline,
  className = "",
  height = 120,
}: SegmentMiniMapProps): JSX.Element {
  const { url: tileUrl, attribution } = useTileConfig();
  const positions = useMemo<[number, number][]>(() => decodePolyline(polyline), [polyline]);
  const style = { minHeight: height };

  if (positions.length < 2) {
    return <div className={`bg-muted ${className}`} style={style} />;
  }

  return (
    <MapContainer center={positions[0]} zoom={12} className={`h-full w-full ${className}`} style={style}>
      <TileLayer url={tileUrl} attribution={attribution} />
      <Polyline positions={positions} pathOptions={{ color: "#f97316", weight: 3 }} />
      <FitToPositions positions={positions} />
    </MapContainer>
  );
}
