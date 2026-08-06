/**
 * Lightweight SVG component for rendering GPS polylines with a real tile map background.
 *
 * Unlike MiniMap which uses Leaflet tiles, this renders the route as a
 * pure SVG path - much faster for list views with many activities.
 *
 * When showMapBackground is true, displays a grid of OSM raster tiles
 * composited behind the SVG route overlay.
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
  /** Show static map background (default: true) */
  showMapBackground?: boolean;
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
): { path: string; startX: number; startY: number; endX: number; endY: number; bounds: { minLat: number; maxLat: number; minLon: number; maxLon: number } } {
  if (coords.length < 2) {
    return { path: "", startX: 0, startY: 0, endX: 0, endY: 0, bounds: { minLat: 0, maxLat: 0, minLon: 0, maxLon: 0 } };
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
    bounds: { minLat, maxLat, minLon, maxLon },
  };
}

/**
 * Calculate the appropriate zoom level for OSM tiles to fit the bounding box.
 */
function calculateZoom(
  minLat: number,
  maxLat: number,
  minLon: number,
  maxLon: number,
  mapWidth: number,
  mapHeight: number
): number {
  const WORLD_DIM = { height: 256, width: 256 };
  const ZOOM_MAX = 18;

  function latRad(lat: number) {
    const sin = Math.sin((lat * Math.PI) / 180);
    const radX2 = Math.log((1 + sin) / (1 - sin)) / 2;
    return Math.max(Math.min(radX2, Math.PI), -Math.PI) / 2;
  }

  function zoom(mapPx: number, worldPx: number, fraction: number) {
    return Math.floor(Math.log(mapPx / worldPx / fraction) / Math.LN2);
  }

  const latFraction = (latRad(maxLat) - latRad(minLat)) / Math.PI;
  const lonDiff = maxLon - minLon;
  const lonFraction = (lonDiff < 0 ? lonDiff + 360 : lonDiff) / 360;

  const latZoom = zoom(mapHeight, WORLD_DIM.height, latFraction);
  const lonZoom = zoom(mapWidth, WORLD_DIM.width, lonFraction);

  return Math.min(latZoom, lonZoom, ZOOM_MAX);
}

/** Tile size in pixels (standard OSM/CartoDB tile size). */
const TILE_SIZE = 256;

/** A single tile's grid coordinates and its CSS-pixel position within the container. */
interface TilePosition {
  tileX: number;
  tileY: number;
  /** Left offset in pixels from the container's top-left corner. */
  left: number;
  /** Top offset in pixels from the container's top-left corner. */
  top: number;
}

/** Result of getTileGrid: the list of tiles to render and the zoom level used. */
interface TileGrid {
  tiles: TilePosition[];
  zoom: number;
}

/** Convert longitude to tile X at the given zoom level. */
function lonToTileX(lon: number, zoom: number): number {
  return ((lon + 180) / 360) * Math.pow(2, zoom);
}

/** Convert latitude to tile Y at the given zoom level. */
function latToTileY(lat: number, zoom: number): number {
  const rad = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * Math.pow(2, zoom);
}

/**
 * Calculate the tile grid needed to fill a container of the given dimensions,
 * centred on the provided lat/lon at the best-fit zoom level.
 */
function getTileGrid(
  minLat: number,
  maxLat: number,
  minLon: number,
  maxLon: number,
  containerWidth: number,
  containerHeight: number,
): TileGrid {
  // Add 15 % padding around the route bounds
  const latPad = (maxLat - minLat) * 0.2;
  const lonPad = (maxLon - minLon) * 0.2;
  const pMinLat = minLat - latPad;
  const pMaxLat = maxLat + latPad;
  const pMinLon = minLon - lonPad;
  const pMaxLon = maxLon + lonPad;

  const zoom = Math.max(1, Math.min(18, calculateZoom(pMinLat, pMaxLat, pMinLon, pMaxLon, containerWidth, containerHeight)));

  const centerLat = (pMinLat + pMaxLat) / 2;
  const centerLon = (pMinLon + pMaxLon) / 2;

  // Fractional tile coordinates of the centre
  const centerTileX = lonToTileX(centerLon, zoom);
  const centerTileY = latToTileY(centerLat, zoom);

  // Pixel position of the centre within the tile grid origin
  const centerPixelX = centerTileX * TILE_SIZE;
  const centerPixelY = centerTileY * TILE_SIZE;

  // Top-left pixel of the container
  const originPixelX = centerPixelX - containerWidth / 2;
  const originPixelY = centerPixelY - containerHeight / 2;

  // Integer tile range to cover the container
  const startTileX = Math.floor(originPixelX / TILE_SIZE);
  const startTileY = Math.floor(originPixelY / TILE_SIZE);
  const endTileX = Math.ceil((originPixelX + containerWidth) / TILE_SIZE);
  const endTileY = Math.ceil((originPixelY + containerHeight) / TILE_SIZE);

  const maxTile = Math.pow(2, zoom) - 1;

  const tiles: TilePosition[] = [];

  for (let tx = startTileX; tx <= endTileX; tx++) {
    for (let ty = startTileY; ty <= endTileY; ty++) {
      // Clamp to valid tile range
      const clampedTx = Math.max(0, Math.min(maxTile, tx));
      const clampedTy = Math.max(0, Math.min(maxTile, ty));

      const left = tx * TILE_SIZE - originPixelX;
      const top = ty * TILE_SIZE - originPixelY;

      tiles.push({ tileX: clampedTx, tileY: clampedTy, left, top });
    }
  }

  return { tiles, zoom };
}

export function PolylineMap({
  polyline,
  className = "",
  strokeColor = "#6366f1",
  strokeWidth = 2,
  showMarkers = true,
  showMapBackground = true,
}: PolylineMapProps) {
  // Decode polyline
  const coords = polyline ? decodePolyline(polyline) : [];

  if (coords.length < 2) {
    return (
      <div className={`bg-muted rounded flex items-center justify-center ${className}`}>
        <span className="text-xs text-muted-foreground">No GPS</span>
      </div>
    );
  }

  // Use a standard size for the SVG viewBox
  const svgWidth = 150;
  const svgHeight = 100;
  const { path, startX, startY, endX, endY, bounds } = coordsToSvgPath(coords, svgWidth, svgHeight);
  
  // Generate tile grid if background is enabled
  // Container dimensions in real pixels (2× the SVG viewBox to get crisper tiles)
  const containerW = 300;
  const containerH = 200;
  const tileGrid: TileGrid | null = showMapBackground
    ? getTileGrid(bounds.minLat, bounds.maxLat, bounds.minLon, bounds.maxLon, containerW, containerH)
    : null;

  // OSM tile base URL via backend proxy
  const tileBase = "/tiles";

  return (
    <div className={`relative rounded overflow-hidden ${className}`}>
      {/* Tile map background */}
      {tileGrid && (
        <div className="absolute inset-0 overflow-hidden">
          {tileGrid.tiles.map(({ tileX, tileY, left, top }) => {
            // Scale from container pixels to CSS pixels (50 % because containerW = 2 × svgWidth)
            const cssLeft = (left / containerW) * 100;
            const cssTop = (top / containerH) * 100;
            const cssSize = (TILE_SIZE / containerW) * 100;
            return (
              <img
                key={`${tileGrid.zoom}-${tileX}-${tileY}`}
                src={`${tileBase}/${tileGrid.zoom}/${tileX}/${tileY}.png`}
                alt=""
                className="absolute block"
                style={{
                  left: `${cssLeft}%`,
                  top: `${cssTop}%`,
                  width: `${cssSize}%`,
                  height: "auto",
                  aspectRatio: "1",
                  imageRendering: "auto",
                }}
                loading="lazy"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.visibility = "hidden";
                }}
              />
            );
          })}
        </div>
      )}
      {/* Fallback background when no tiles */}
      {!tileGrid && <div className="absolute inset-0 bg-muted" />}

      {/* SVG overlay with route */}
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="relative w-full h-full"
      >
        {/* Route path with shadow for visibility on map */}
        <path
          d={path}
          fill="none"
          stroke="white"
          strokeWidth={strokeWidth + 2}
          strokeLinecap="round"
          strokeLinejoin="round"
          opacity={0.8}
        />
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
