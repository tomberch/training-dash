import { MapContainer, Polyline, TileLayer, Marker, CircleMarker, useMap } from "react-leaflet";
import type { LatLngBounds } from "leaflet";
import L from "leaflet";
import { useEffect, useRef } from "react";
import { useTheme } from "@/hooks/useTheme";

// Component to fit map bounds to polyline - only runs once on initial load
function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  const hasFitted = useRef(false);
  
  useEffect(() => {
    if (positions.length > 0 && !hasFitted.current) {
      const bounds: LatLngBounds = L.latLngBounds(positions.map(p => L.latLng(p[0], p[1])));
      map.fitBounds(bounds, { padding: [20, 20] });
      hasFitted.current = true;
    }
  }, [map, positions]);
  
  return null;
}

// Invalidate map size when container resizes
function InvalidateOnResize() {
  const map = useMap();
  
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      map.invalidateSize();
    });
    
    const container = map.getContainer();
    if (container) {
      observer.observe(container);
    }
    
    return () => observer.disconnect();
  }, [map]);
  
  return null;
}

interface ColoredSegment {
  positions: [number, number][];
  color: string;
}

interface ResizableMapProps {
  positions: [number, number][];
  coloredSegments?: ColoredSegment[];
  otherPositions?: [number, number][] | null;
  hoveredPosition?: [number, number] | null;
  height: number;
  onResizeStart: (e: React.MouseEvent) => void;
  isResizing: boolean;
  showResizeHandle?: boolean;
}

export function ResizableMap({
  positions,
  coloredSegments = [],
  otherPositions,
  hoveredPosition,
  height,
  onResizeStart,
  isResizing,
  showResizeHandle = true,
}: ResizableMapProps) {
  const { resolvedTheme } = useTheme();
  
  if (positions.length === 0) return null;

  const center: [number, number] = [
    positions.reduce((sum, p) => sum + p[0], 0) / positions.length,
    positions.reduce((sum, p) => sum + p[1], 0) / positions.length,
  ];

  // Theme-aware tile URLs — routed through the backend proxy for caching
  const tileUrl = resolvedTheme === "mocha"
    ? "/tiles/carto/dark/{z}/{x}/{y}.png"
    : "/tiles/carto/light/{z}/{x}/{y}.png";
  
  const attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';

  return (
    <div className="relative bg-card rounded-lg border border-border overflow-hidden">
      <MapContainer
        center={center}
        zoom={13}
        style={{ height: `${height}px`, width: "100%" }}
      >
        <TileLayer
          url={tileUrl}
          attribution={attribution}
        />
        <FitBounds positions={positions} />
        <InvalidateOnResize />
        
        {coloredSegments.length > 0
          ? coloredSegments.map((seg, i) => (
              <Polyline key={i} positions={seg.positions} color={seg.color} weight={4} />
            ))
          : <Polyline positions={positions} color="#6366f1" weight={5} />}
        
        {otherPositions && (
          <Polyline positions={otherPositions} color="#f59e0b" weight={3} dashArray="5,5" />
        )}
        
        {/* Start marker */}
        <Marker
          position={positions[0]}
          icon={L.divIcon({
            className: "",
            html: `<div style="background:#10b981;width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="white"><polygon points="8,5 19,12 8,19"/></svg>
            </div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          })}
        />
        
        {/* End marker */}
        <Marker
          position={positions[positions.length - 1]}
          icon={L.divIcon({
            className: "",
            html: `<div style="background:#ef4444;width:24px;height:24px;border-radius:50%;border:3px solid white;box-shadow:0 2px 4px rgba(0,0,0,0.3);display:flex;align-items:center;justify-content:center;">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="white"><rect x="6" y="6" width="12" height="12"/></svg>
            </div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
          })}
        />
        
        {/* Hover position marker */}
        {hoveredPosition && (
          <CircleMarker
            center={hoveredPosition}
            radius={8}
            pathOptions={{
              color: "#ffffff",
              weight: 3,
              fillColor: "#f59e0b",
              fillOpacity: 1,
            }}
          />
        )}
      </MapContainer>
      
      {/* Resize handle */}
      {showResizeHandle && (
        <div
          onMouseDown={onResizeStart}
          className={`absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize flex items-center justify-center group ${
            isResizing ? "bg-primary/20" : "hover:bg-muted"
          }`}
        >
          <div className={`w-12 h-1 rounded-full transition-colors ${
            isResizing 
              ? "bg-primary" 
              : "bg-muted-foreground/30 group-hover:bg-muted-foreground/50"
          }`} />
        </div>
      )}
    </div>
  );
}
