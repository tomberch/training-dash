/**
 * Lightweight SVG component for rendering GPS polylines.
 * 
 * Unlike MiniMap which uses Leaflet tiles, this renders the route as a
 * pure SVG path - much faster for list views with many activities.
 */

interface PolylineMapProps {
  /** Google-encoded polyline string */
  polyline: string | null | undefined;
  /** Additional CSS classes */
  className?: string;
  /** Stroke color (default: indigo) */
  strokeColor?: string;
  /** Stroke width in pixels */
  strokeWidth?: number;
  /** Show start (green) and end (red) markers */
  showMarkers?: boolean;
}

/**
 * Decode a Google-encoded polyline string to coordinates.
 * https://developers.google.com/maps/documentation/utilities/polylinealgorithm
 */
function decodePolyline(encoded: string, precision: number = 5): [number, number][] {
  if (!encoded) return [];

  const coords: [number, number][] = [];
  let index = 0;
  let lat = 0;
  let lon = 0;
  const factor = Math.pow(10, precision);

  while (index < encoded.length) {
    // Decode latitude
    let shift = 0;
    let result = 0;
    let byte: number;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const dLat = result & 1 ? ~(result >> 1) : result >> 1;
    lat += dLat;

    // Decode longitude
    shift = 0;
    result = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    const dLon = result & 1 ? ~(result >> 1) : result >> 1;
    lon += dLon;

    coords.push([lat / factor, lon / factor]);
  }

  return coords;
}

/**
 * Convert lat/lon coordinates to SVG path coordinates.
 * Uses simple equirectangular projection (good enough for small areas).
 */
function coordsToSvgPath(
  coords: [number, number][],
  width: number,
  height: number,
  padding: number = 8
): { path: string; startX: number; startY: number; endX: number; endY: number } {
  if (coords.length < 2) {
    return { path: "", startX: 0, startY: 0, endX: 0, endY: 0 };
  }

  // Find bounding box
  let minLat = Infinity, maxLat = -Infinity;
  let minLon = Infinity, maxLon = -Infinity;

  for (const [lat, lon] of coords) {
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
  }

  // Handle single point or very small routes
  const latRange = maxLat - minLat || 0.001;
  const lonRange = maxLon - minLon || 0.001;

  // Scale to fit SVG with padding
  const drawWidth = width - padding * 2;
  const drawHeight = height - padding * 2;

  // Maintain aspect ratio (approximate, using cos of center latitude)
  const centerLat = (minLat + maxLat) / 2;
  const lonScale = Math.cos((centerLat * Math.PI) / 180);
  const aspectRatio = (lonRange * lonScale) / latRange;

  let scaleX: number, scaleY: number;
  if (aspectRatio > drawWidth / drawHeight) {
    // Width-constrained
    scaleX = drawWidth / lonRange;
    scaleY = scaleX / lonScale;
  } else {
    // Height-constrained
    scaleY = drawHeight / latRange;
    scaleX = scaleY * lonScale;
  }

  // Center the route
  const routeWidth = lonRange * scaleX;
  const routeHeight = latRange * scaleY;
  const offsetX = padding + (drawWidth - routeWidth) / 2;
  const offsetY = padding + (drawHeight - routeHeight) / 2;

  // Convert to SVG coordinates (flip Y axis)
  const toSvg = (lat: number, lon: number): [number, number] => [
    offsetX + (lon - minLon) * scaleX,
    offsetY + (maxLat - lat) * scaleY,
  ];

  // Build SVG path
  const pathParts: string[] = [];
  const [startX, startY] = toSvg(coords[0][0], coords[0][1]);
  pathParts.push(`M ${startX.toFixed(1)} ${startY.toFixed(1)}`);

  for (let i = 1; i < coords.length; i++) {
    const [x, y] = toSvg(coords[i][0], coords[i][1]);
    pathParts.push(`L ${x.toFixed(1)} ${y.toFixed(1)}`);
  }

  const [endX, endY] = toSvg(coords[coords.length - 1][0], coords[coords.length - 1][1]);

  return {
    path: pathParts.join(" "),
    startX,
    startY,
    endX,
    endY,
  };
}

export function PolylineMap({
  polyline,
  className = "",
  strokeColor = "#6366f1",
  strokeWidth = 2,
  showMarkers = true,
}: PolylineMapProps) {
  // Decode polyline
  const coords = polyline ? decodePolyline(polyline) : [];

  if (coords.length < 2) {
    return (
      <div className={`bg-gray-100 dark:bg-gray-700 rounded flex items-center justify-center ${className}`}>
        <span className="text-xs text-gray-400 dark:text-gray-500">No GPS</span>
      </div>
    );
  }

  // Use a standard size for the SVG viewBox
  const svgWidth = 150;
  const svgHeight = 100;
  const { path, startX, startY, endX, endY } = coordsToSvgPath(coords, svgWidth, svgHeight);

  return (
    <div className={`bg-gray-100 dark:bg-gray-800 rounded overflow-hidden ${className}`}>
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="w-full h-full"
      >
        {/* Route path */}
        <path
          d={path}
          fill="none"
          stroke={strokeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Start and end markers */}
        {showMarkers && (
          <>
            {/* Start marker (green) */}
            <circle
              cx={startX}
              cy={startY}
              r={4}
              fill="#10b981"
              stroke="white"
              strokeWidth={1.5}
            />
            {/* End marker (red) */}
            <circle
              cx={endX}
              cy={endY}
              r={4}
              fill="#ef4444"
              stroke="white"
              strokeWidth={1.5}
            />
          </>
        )}
      </svg>
    </div>
  );
}

export { decodePolyline };
