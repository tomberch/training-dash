import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Brush,
} from "recharts";
import type { Activity, GeoJSONFeatureCollection, ThresholdEntry } from "../api";
import { fetchActivity, fetchActivityRecords, fetchThresholds } from "../api";
import { ActivitySelector } from "../components/ActivitySelector";
import { ResizableMap } from "../components/ResizableMap";
import { useResizableMap } from "../hooks/useResizableMap";
import { ChartErrorBoundary } from "../components/ErrorBoundary";

type AxisMode = "time" | "distance";
type SmoothingLevel = "raw" | "10s" | "30s";

interface SeriesConfig {
  key: string;
  label: string;
  color: string;
  dataKey: string;
  unit: string;
  yAxisId: "left" | "right";
  type: "line" | "area";
}

const SERIES_CONFIG: SeriesConfig[] = [
  { key: "power", label: "Power", color: "#f59e0b", dataKey: "power_w", unit: "W", yAxisId: "left", type: "line" },
  { key: "hr", label: "HR", color: "#ef4444", dataKey: "hr_bpm", unit: "bpm", yAxisId: "left", type: "line" },
  { key: "speed", label: "Speed", color: "#3b82f6", dataKey: "speed_mps", unit: "km/h", yAxisId: "right", type: "line" },
  { key: "cadence", label: "Cadence", color: "#8b5cf6", dataKey: "cadence_rpm", unit: "rpm", yAxisId: "left", type: "line" },
  { key: "elevation", label: "Elevation", color: "#10b981", dataKey: "altitude_m", unit: "m", yAxisId: "right", type: "area" },
];

interface ChartDataPoint {
  distance_m: number;
  elapsed: number;
  power_w: number | null;
  hr_bpm: number | null;
  speed_mps: number | null;
  cadence_rpm: number | null;
  altitude_m: number | null;
}

function formatElapsedTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatDistanceKm(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

// Apply rolling average smoothing
function smoothData(data: ChartDataPoint[], windowSeconds: number, timestamps: number[]): ChartDataPoint[] {
  if (windowSeconds === 0 || data.length === 0) return data;
  
  return data.map((point, i) => {
    const currentTime = timestamps[i];
    const windowStart = currentTime - windowSeconds;
    
    // Find points within the window
    let startIdx = i;
    while (startIdx > 0 && timestamps[startIdx - 1] >= windowStart) {
      startIdx--;
    }
    
    const windowPoints = data.slice(startIdx, i + 1);
    const count = windowPoints.length;
    
    const avgPower = windowPoints.reduce((sum, p) => sum + (p.power_w ?? 0), 0) / count;
    const avgHr = windowPoints.reduce((sum, p) => sum + (p.hr_bpm ?? 0), 0) / count;
    const avgSpeed = windowPoints.reduce((sum, p) => sum + (p.speed_mps ?? 0), 0) / count;
    const avgCadence = windowPoints.reduce((sum, p) => sum + (p.cadence_rpm ?? 0), 0) / count;
    
    return {
      ...point,
      power_w: point.power_w !== null ? avgPower : null,
      hr_bpm: point.hr_bpm !== null ? avgHr : null,
      speed_mps: point.speed_mps !== null ? avgSpeed : null,
      cadence_rpm: point.cadence_rpm !== null ? avgCadence : null,
      // Don't smooth elevation - it's already smooth
    };
  });
}

export function AnalyzePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activityIdParam = searchParams.get("activity");
  const [selectedActivity, setSelectedActivity] = useState<Activity | null>(null);
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [axisMode, setAxisMode] = useState<AxisMode>("time");
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);
  
  // Overlay control state
  const [visibleSeries, setVisibleSeries] = useState<Set<string>>(new Set());
  const [smoothing, setSmoothing] = useState<SmoothingLevel>("raw");
  const [showZoneThresholds, setShowZoneThresholds] = useState(false);
  const [zoomDomain, setZoomDomain] = useState<{ start: number; end: number } | null>(null);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const loadedFromUrl = useRef(false);
  const initialSeriesSet = useRef(false);

  // Resizable map with separate localStorage key for Analyze page
  const {
    height: mapHeight,
    isResizing,
    startResizeHeight,
  } = useResizableMap({
    storageKey: "analyze-page",
    defaultHeight: 250,
    minHeight: 150,
    maxHeight: 400,
    defaultWidthPercent: 40,
    minWidthPercent: 25,
    maxWidthPercent: 60,
  });

  // Load activity from URL param on mount
  useEffect(() => {
    if (activityIdParam && !loadedFromUrl.current) {
      loadedFromUrl.current = true;
      setLoading(true);
      Promise.all([fetchActivity(activityIdParam), fetchActivityRecords(activityIdParam), fetchThresholds()])
        .then(([activity, records, th]) => {
          setSelectedActivity(activity);
          setGeojson(records);
          setThresholds(th);
          setError(null);
        })
        .catch((e) => {
          console.error("[AnalyzePage] Failed to load activity from URL:", e);
          setError("Failed to load activity");
          setSearchParams({});
        })
        .finally(() => setLoading(false));
    }
  }, [activityIdParam, setSearchParams]);

  const handleActivitySelect = (activity: Activity | null) => {
    setSelectedActivity(activity);
    setGeojson(null);
    setHoveredPosition(null);
    setZoomDomain(null);
    initialSeriesSet.current = false; // Reset so we auto-select first available series
    
    if (activity) {
      setSearchParams({ activity: activity.id.toString() });
      setLoading(true);
      Promise.all([fetchActivityRecords(activity.id), fetchThresholds()])
        .then(([records, th]) => {
          setGeojson(records);
          setThresholds(th);
          setError(null);
        })
        .catch((e) => {
          console.error("[AnalyzePage] Failed to load activity records:", e);
          setError("Failed to load activity data");
        })
        .finally(() => setLoading(false));
    } else {
      setSearchParams({});
    }
  };

  // Toggle series visibility
  const toggleSeries = useCallback((key: string) => {
    setVisibleSeries((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  // Reset zoom
  const resetZoom = useCallback(() => {
    setZoomDomain(null);
  }, []);

  // Extract positions for map
  const positions = useMemo(() => {
    if (!geojson) return [];
    return geojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
  }, [geojson]);

  // Extract timestamps for elapsed time calculation
  const timestamps = useMemo(() => {
    if (!geojson) return [];
    return geojson.features.map((f) => new Date(f.properties.timestamp).getTime() / 1000);
  }, [geojson]);

  const firstTs = timestamps.length > 0 ? timestamps[0] : 0;

  // Build chart data with all metrics
  const rawChartData = useMemo((): ChartDataPoint[] => {
    if (!geojson || timestamps.length === 0) return [];
    return geojson.features.map((f, i) => ({
      distance_m: f.properties.distance_m,
      elapsed: timestamps[i] - firstTs,
      power_w: f.properties.power_w,
      hr_bpm: f.properties.hr_bpm,
      speed_mps: f.properties.speed_mps ? f.properties.speed_mps * 3.6 : null, // Convert to km/h
      cadence_rpm: f.properties.cadence_rpm,
      altitude_m: f.properties.altitude_m,
    }));
  }, [geojson, timestamps, firstTs]);

  // Apply smoothing
  const chartData = useMemo(() => {
    const windowSeconds = smoothing === "raw" ? 0 : smoothing === "10s" ? 10 : 30;
    return smoothData(rawChartData, windowSeconds, timestamps);
  }, [rawChartData, smoothing, timestamps]);

  // Get applicable threshold for the activity date
  const applicableThreshold = useMemo(() => {
    if (!selectedActivity || thresholds.length === 0) return null;
    const activityDate = new Date(selectedActivity.started_at).toISOString().split("T")[0];
    const applicable = thresholds.find((t) => t.effective_date <= activityDate);
    return applicable ?? thresholds[thresholds.length - 1];
  }, [selectedActivity, thresholds]);

  const ftpWatts = applicableThreshold?.ftp_watts ?? null;
  const lthrBpm = applicableThreshold?.lthr_bpm ?? null;

  // Position lookup by distance for hover sync
  const posByDist = useMemo(() => {
    if (!geojson) return [];
    return geojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => ({
        distance_m: f.properties.distance_m,
        pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
      }));
  }, [geojson]);

  // Position lookup by elapsed time
  const posByElapsed = useMemo(() => {
    if (!geojson || timestamps.length === 0) return [];
    return geojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f, i) => ({
        elapsed: timestamps[i] - firstTs,
        pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
      }));
  }, [geojson, timestamps, firstTs]);

  const findPositionByDistance = (distance_m: number): [number, number] | null => {
    if (posByDist.length === 0) return null;
    let closest = posByDist[0];
    let minDiff = Math.abs(closest.distance_m - distance_m);
    for (const p of posByDist) {
      const diff = Math.abs(p.distance_m - distance_m);
      if (diff < minDiff) {
        minDiff = diff;
        closest = p;
      }
    }
    return closest.pos;
  };

  const findPositionByElapsed = (elapsed: number): [number, number] | null => {
    if (posByElapsed.length === 0) return null;
    let closest = posByElapsed[0];
    let minDiff = Math.abs(closest.elapsed - elapsed);
    for (const p of posByElapsed) {
      const diff = Math.abs(p.elapsed - elapsed);
      if (diff < minDiff) {
        minDiff = diff;
        closest = p;
      }
    }
    return closest.pos;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleChartHover = (state: any) => {
    if (state?.activePayload?.[0]?.payload) {
      const point = state.activePayload[0].payload as ChartDataPoint;
      const pos = axisMode === "distance"
        ? findPositionByDistance(point.distance_m)
        : findPositionByElapsed(point.elapsed);
      setHoveredPosition(pos);
    }
  };

  const handleChartLeave = () => {
    setHoveredPosition(null);
  };

  // Handle brush change for zoom
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleBrushChange = (brushArea: any) => {
    if (brushArea && brushArea.startIndex !== undefined && brushArea.endIndex !== undefined) {
      setZoomDomain({ start: brushArea.startIndex, end: brushArea.endIndex });
    }
  };

  // Check which data series are available
  const availableSeries = useMemo(() => {
    const available: Set<string> = new Set();
    for (const point of rawChartData) {
      if (point.power_w !== null) available.add("power");
      if (point.hr_bpm !== null) available.add("hr");
      if (point.speed_mps !== null) available.add("speed");
      if (point.cadence_rpm !== null) available.add("cadence");
      if (point.altitude_m !== null) available.add("elevation");
    }
    return available;
  }, [rawChartData]);

  // Auto-select first available series when data loads
  useEffect(() => {
    if (availableSeries.size > 0 && !initialSeriesSet.current) {
      initialSeriesSet.current = true;
      // Priority order: power, hr, speed, cadence, elevation
      const priorityOrder = ["power", "hr", "speed", "cadence", "elevation"];
      const firstAvailable = priorityOrder.find((key) => availableSeries.has(key));
      if (firstAvailable) {
        setVisibleSeries(new Set([firstAvailable]));
      }
    }
  }, [availableSeries]);

  // Check if zones are available (FTP for power, LTHR for HR)
  const hasZonesAvailable = useMemo(() => {
    return (ftpWatts !== null && availableSeries.has("power")) || 
           (lthrBpm !== null && availableSeries.has("hr"));
  }, [ftpWatts, lthrBpm, availableSeries]);

  // Check if any visible series has data
  const hasVisibleData = useMemo(() => {
    for (const key of visibleSeries) {
      if (availableSeries.has(key)) return true;
    }
    return false;
  }, [visibleSeries, availableSeries]);

  // Compute stable Y-axis domains based on the full data range (not affected by smoothing)
  const yAxisDomains = useMemo(() => {
    const leftValues: number[] = [];
    const rightValues: number[] = [];
    
    for (const point of rawChartData) {
      // Left axis: power, hr, cadence
      if (visibleSeries.has("power") && point.power_w !== null) leftValues.push(point.power_w);
      if (visibleSeries.has("hr") && point.hr_bpm !== null) leftValues.push(point.hr_bpm);
      if (visibleSeries.has("cadence") && point.cadence_rpm !== null) leftValues.push(point.cadence_rpm);
      
      // Right axis: speed, elevation
      if (visibleSeries.has("speed") && point.speed_mps !== null) leftValues.push(point.speed_mps); // speed in km/h from rawChartData
      if (visibleSeries.has("elevation") && point.altitude_m !== null) rightValues.push(point.altitude_m);
    }
    
    const computeDomain = (values: number[]): [number, number] => {
      if (values.length === 0) return [0, 100];
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;
      const padding = range * 0.05;
      return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
    };
    
    return {
      left: computeDomain(leftValues),
      right: computeDomain(rightValues),
    };
  }, [rawChartData, visibleSeries]);

  return (
    <div ref={containerRef} className="h-full flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Sticky map */}
      {selectedActivity && positions.length > 0 && (
        <div className="flex-shrink-0 p-4 pb-0">
          <ResizableMap
            positions={positions}
            hoveredPosition={hoveredPosition}
            height={mapHeight}
            onResizeStart={startResizeHeight}
            isResizing={isResizing}
          />
        </div>
      )}

      {/* Control bar */}
      <div className="flex-shrink-0 p-4">
        <div className="flex flex-col gap-3">
          {/* Row 1: Activity selector */}
          <div className="flex flex-col sm:flex-row sm:items-end gap-4">
            <div className="flex-1 max-w-md">
              <ActivitySelector
                selectedId={selectedActivity?.id ?? null}
                onSelect={handleActivitySelect}
                label="Select Activity"
                placeholder="Search for an activity..."
              />
            </div>
          </div>
          
          {/* Row 2: Chart controls (only shown when activity is loaded) */}
          {selectedActivity && geojson && (
            <div className="flex flex-wrap items-center gap-4 p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
              {/* Series toggles - only show available series */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Series:</span>
                {SERIES_CONFIG.filter((series) => availableSeries.has(series.key)).map((series) => (
                  <button
                    key={series.key}
                    onClick={() => toggleSeries(series.key)}
                    className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                      visibleSeries.has(series.key)
                        ? "text-white"
                        : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600"
                    }`}
                    style={visibleSeries.has(series.key) ? { backgroundColor: series.color } : undefined}
                  >
                    {series.label}
                  </button>
                ))}
              </div>

              <div className="w-px h-6 bg-gray-300 dark:bg-gray-600" />

              {/* Smoothing */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">Smooth:</span>
                {(["raw", "10s", "30s"] as SmoothingLevel[]).map((level) => (
                  <button
                    key={level}
                    onClick={() => setSmoothing(level)}
                    className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                      smoothing === level
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600"
                    }`}
                  >
                    {level === "raw" ? "Raw" : level}
                  </button>
                ))}
              </div>

              <div className="w-px h-6 bg-gray-300 dark:bg-gray-600" />

              {/* X-axis toggle */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">X-axis:</span>
                <button
                  onClick={() => setAxisMode(axisMode === "time" ? "distance" : "time")}
                  className="px-2 py-1 text-xs font-medium rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                >
                  {axisMode === "time" ? "Time" : "Distance"}
                </button>
              </div>

              {/* Zone thresholds toggle - only show if zones are available */}
              {hasZonesAvailable && (
                <>
                  <div className="w-px h-6 bg-gray-300 dark:bg-gray-600" />
                  <button
                    onClick={() => setShowZoneThresholds(!showZoneThresholds)}
                    className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                      showZoneThresholds
                        ? "bg-indigo-600 text-white"
                        : "bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-300 dark:hover:bg-gray-600"
                    }`}
                  >
                    Zones
                  </button>
                </>
              )}

              {/* Lap markers toggle - hidden for now since lap data isn't available */}
              {/* Future: Show this when activity.laps is available */}

              {/* Zoom reset */}
              {zoomDomain && (
                <button
                  onClick={resetZoom}
                  className="px-2 py-1 text-xs font-medium rounded bg-amber-600 text-white hover:bg-amber-700 transition-colors"
                >
                  Reset Zoom
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Chart area - fills remaining viewport */}
      <div className="flex-1 min-h-0 p-4 pt-0">
        {loading ? (
          <div className="h-full flex items-center justify-center bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Loading activity data...
            </div>
          </div>
        ) : error ? (
          <div className="h-full flex items-center justify-center bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="text-center">
              <p className="text-red-500 dark:text-red-400 mb-2">{error}</p>
              <button
                onClick={() => selectedActivity && handleActivitySelect(selectedActivity)}
                className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                Try again
              </button>
            </div>
          </div>
        ) : selectedActivity && geojson ? (
          <ChartErrorBoundary>
            <div className="h-full bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
              {hasVisibleData ? (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={chartData}
                    onMouseMove={handleChartHover}
                    onMouseLeave={handleChartLeave}
                    margin={{ top: 10, right: 60, left: 10, bottom: 30 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                    <XAxis
                      dataKey={axisMode === "distance" ? "distance_m" : "elapsed"}
                      tickFormatter={axisMode === "distance" ? formatDistanceKm : formatElapsedTime}
                      stroke="#9ca3af"
                      fontSize={12}
                    />
                    
                    {/* Left Y-axis for Power/HR/Cadence */}
                    <YAxis
                      yAxisId="left"
                      stroke="#9ca3af"
                      fontSize={12}
                      domain={yAxisDomains.left}
                      allowDataOverflow={false}
                      tickFormatter={(v) => Math.round(v).toString()}
                    />
                    
                    {/* Right Y-axis for Speed/Elevation */}
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      stroke="#9ca3af"
                      fontSize={12}
                      domain={yAxisDomains.right}
                      allowDataOverflow={false}
                      tickFormatter={(v) => Math.round(v).toString()}
                    />
                    
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "0.375rem",
                        color: "#f9fafb",
                      }}
                      formatter={(value, name) => {
                        const series = SERIES_CONFIG.find((s) => s.dataKey === name);
                        if (!series) return [value, name];
                        const formatted = typeof value === "number" ? Math.round(value) : value;
                        return [`${formatted} ${series.unit}`, series.label];
                      }}
                      labelFormatter={(label) =>
                        axisMode === "distance"
                          ? formatDistanceKm(label as number)
                          : formatElapsedTime(label as number)
                      }
                    />
                    
                    {/* Zone threshold lines */}
                    {showZoneThresholds && ftpWatts && visibleSeries.has("power") && (
                      <ReferenceLine
                        y={ftpWatts}
                        yAxisId="left"
                        stroke="#f59e0b"
                        strokeDasharray="5 5"
                        strokeWidth={2}
                        label={{ value: `FTP: ${ftpWatts}W`, fill: "#f59e0b", fontSize: 11, position: "right" }}
                      />
                    )}
                    {showZoneThresholds && lthrBpm && visibleSeries.has("hr") && (
                      <ReferenceLine
                        y={lthrBpm}
                        yAxisId="left"
                        stroke="#ef4444"
                        strokeDasharray="5 5"
                        strokeWidth={2}
                        label={{ value: `LTHR: ${lthrBpm}`, fill: "#ef4444", fontSize: 11, position: "right" }}
                      />
                    )}
                    
                    {/* Render elevation as area first (background) */}
                    {visibleSeries.has("elevation") && availableSeries.has("elevation") && (
                      <Area
                        type="monotone"
                        dataKey="altitude_m"
                        yAxisId="right"
                        fill="#10b981"
                        fillOpacity={0.2}
                        stroke="#10b981"
                        strokeWidth={1}
                      />
                    )}
                    
                    {/* Render line series */}
                    {SERIES_CONFIG.filter((s) => s.type === "line").map((series) =>
                      visibleSeries.has(series.key) && availableSeries.has(series.key) ? (
                        <Line
                          key={series.key}
                          type="monotone"
                          dataKey={series.dataKey}
                          yAxisId={series.yAxisId}
                          stroke={series.color}
                          strokeWidth={1.5}
                          dot={false}
                          connectNulls
                        />
                      ) : null
                    )}
                    
                    {/* Brush for zoom */}
                    <Brush
                      dataKey={axisMode === "distance" ? "distance_m" : "elapsed"}
                      height={20}
                      stroke="#6366f1"
                      fill="#1f2937"
                      tickFormatter={axisMode === "distance" ? formatDistanceKm : formatElapsedTime}
                      onChange={handleBrushChange}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500 dark:text-gray-400">
                  No data available for selected series. Try enabling different metrics.
                </div>
              )}
            </div>
          </ChartErrorBoundary>
        ) : (
          <div className="h-full flex items-center justify-center bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <p className="text-gray-500 dark:text-gray-400">
              Select an activity above to begin analysis.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
