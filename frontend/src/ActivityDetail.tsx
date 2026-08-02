import { useState, useEffect, useMemo, useRef } from "react";
import { MapContainer, Polyline, TileLayer, useMap, Marker, CircleMarker } from "react-leaflet";
import type { LatLngBounds } from "leaflet";
import L from "leaflet";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
  ReferenceArea,
} from "recharts";
import type { Activity, GeoJSONFeatureCollection, CompareResponse, SameRouteResponse, GapPoint, WbalResponse } from "./api";
import { ApiError, fetchActivity, fetchActivityRecords, fetchActivityWbal, fetchSameRouteActivities, fetchComparison } from "./api";
import { formatDistance, formatTime, formatElevation, formatSpeed } from "./format";
import type { UnitSystem } from "./format";
import { resampleByDistance } from "./resampler";
import type { FitRecord } from "./resampler";
import { ErrorDisplay } from "./ErrorDisplay";

type AxisMode = "time" | "distance";

function gapColor(gap: number): string {
  if (gap < -0.5) return "#10b981"; // green = faster
  if (gap > 0.5) return "#ef4444"; // red = slower
  return "#6366f1"; // neutral indigo
}

function positionsByDistance(gpsFeatures: GeoJSONFeatureCollection["features"]): { distance_m: number; pos: [number, number] }[] {
  return gpsFeatures
    .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
    .map((f) => ({
      distance_m: f.properties.distance_m,
      pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
    }));
}

function buildColoredSegments(
  gapSeries: GapPoint[],
  posByDist: { distance_m: number; pos: [number, number] }[]
): { positions: [number, number][]; color: string }[] {
  if (gapSeries.length < 2 || posByDist.length < 2) return [];

  const segments: { positions: [number, number][]; color: string }[] = [];

  for (let i = 0; i < gapSeries.length - 1; i++) {
    const distStart = gapSeries[i].distance_m;
    const distEnd = gapSeries[i + 1].distance_m;
    const color = gapColor(gapSeries[i].gap_s);

    const pointsInSegment: [number, number][] = [];
    for (const p of posByDist) {
      if (p.distance_m >= distStart && p.distance_m <= distEnd) {
        pointsInSegment.push(p.pos);
      }
    }
    if (pointsInSegment.length >= 2) {
      segments.push({ positions: pointsInSegment, color });
    }
  }

  return segments;
}

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

interface ChartConfig {
  key: string;
  label: string;
  unit: string;
  color: string;
  dataKey: string;
}

const CHARTS: ChartConfig[] = [
  { key: "speed", label: "Speed", unit: "m/s", color: "#6366f1", dataKey: "speed_mps" },
  { key: "hr", label: "Heart Rate", unit: "bpm", color: "#ef4444", dataKey: "hr_bpm" },
  { key: "power", label: "Power", unit: "W", color: "#f59e0b", dataKey: "power_w" },
  { key: "elevation", label: "Elevation", unit: "m", color: "#10b981", dataKey: "altitude_m" },
];

// Zone colors (matching typical training zone colors)
const POWER_ZONE_COLORS: Record<string, string> = {
  "1": "#9ca3af", // Recovery - gray
  "2": "#3b82f6", // Endurance - blue
  "3": "#22c55e", // Tempo - green
  "4": "#eab308", // Threshold - yellow
  "5": "#f97316", // VO2max - orange
  "6": "#ef4444", // Anaerobic - red
  "7": "#7c3aed", // Neuromuscular - purple
};

const HR_ZONE_COLORS: Record<string, string> = {
  "1": "#9ca3af", // Recovery - gray
  "2": "#3b82f6", // Aerobic - blue
  "3": "#22c55e", // Tempo - green
  "4": "#eab308", // Threshold - yellow
  "5": "#ef4444", // VO2max - red
};

interface Props {
  activityId: number;
  onBack: () => void;
  unitSystem?: UnitSystem;
}

function geojsonToRecords(geojson: GeoJSONFeatureCollection): FitRecord[] {
  return geojson.features.map((f) => ({
    distance_m: f.properties.distance_m,
    hr_bpm: f.properties.hr_bpm,
    power_w: f.properties.power_w,
    speed_mps: f.properties.speed_mps,
    altitude_m: f.properties.altitude_m,
  }));
}

function geojsonToTimestamps(geojson: GeoJSONFeatureCollection): number[] {
  return geojson.features.map((f) => new Date(f.properties.timestamp).getTime() / 1000);
}

export function ActivityDetail({ activityId, onBack, unitSystem = "metric" }: Props) {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [axisModes, setAxisModes] = useState<{ [key: string]: AxisMode }>({
    speed: "time",
    hr: "time",
    power: "time",
    elevation: "time",
  });
  const [sameRoute, setSameRoute] = useState<SameRouteResponse | null>(null);
  const [compareOtherId, setCompareOtherId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [wbalData, setWbalData] = useState<WbalResponse | null>(null);
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);

  useEffect(() => {
    setComparison(null);
    setCompareOtherId(null);
    setWbalData(null);
    Promise.all([
      fetchActivity(activityId),
      fetchActivityRecords(activityId),
      fetchSameRouteActivities(activityId),
      fetchActivityWbal(activityId),
    ])
      .then(([a, g, sr, wbal]) => {
        setActivity(a);
        setGeojson(g);
        setSameRoute(sr);
        setWbalData(wbal);
      })
      .catch((e) => setError(e));
  }, [activityId]);

  useEffect(() => {
    if (compareOtherId === null) {
      setComparison(null);
      return;
    }
    fetchComparison(activityId, compareOtherId)
      .then(setComparison)
      .catch((e) => setError(e));
  }, [activityId, compareOtherId]);

  const records = useMemo(() => (geojson ? geojsonToRecords(geojson) : []), [geojson]);
  const timestamps = useMemo(() => (geojson ? geojsonToTimestamps(geojson) : []), [geojson]);
  const posByDist = useMemo(() => (geojson ? positionsByDistance(geojson.features) : []), [geojson]);
  const firstTs = useMemo(() => timestamps.length > 0 ? timestamps[0] : 0, [timestamps]);

  // Create a lookup for positions by elapsed time
  const posByElapsed = useMemo(() => {
    if (!geojson || timestamps.length === 0) return [];
    const first = timestamps[0];
    return geojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => ({
        elapsed: new Date(f.properties.timestamp).getTime() / 1000 - first,
        pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
      }));
  }, [geojson, timestamps]);

  // Find nearest position for a given elapsed time or distance
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

  const handleChartLeave = () => {
    setHoveredPosition(null);
  };

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
        <div className="max-w-6xl mx-auto">
          <ErrorDisplay error={error} context="loading activity" />
        </div>
      </div>
    );
  }

  if (!activity || !geojson) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  const gpsFeatures = geojson.features.filter(
    (f) => f.geometry !== null && f.geometry.coordinates.length >= 2
  );
  const positions: [number, number][] = gpsFeatures.map((f) => [
    f.geometry!.coordinates[1],
    f.geometry!.coordinates[0],
  ]);

  const center: [number, number] =
    positions.length > 0 ? positions[0] : [47.3769, 8.5417];

  function toggleAxis(chartKey: string) {
    setAxisModes((prev) => ({
      ...prev,
      [chartKey]: prev[chartKey] === "time" ? "distance" : "time",
    }));
  }

  interface ChartDataPoint {
    distance_m: number;
    elapsed: number;
    speed_mps: number | null;
    hr_bpm: number | null;
    power_w: number | null;
    altitude_m: number | null;
  }

  function formatElapsedTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function formatDistanceAxis(meters: number): string {
    if (meters >= 1000) {
      const km = meters / 1000;
      return km % 1 === 0 ? `${km.toFixed(0)} km` : `${km.toFixed(1)} km`;
    }
    return `${meters.toFixed(0)} m`;
  }

  // Heckbert's "nice numbers" algorithm from Graphics Gems
  // Returns a "nice" number approximately equal to range
  // If round is true, round to nearest nice number, otherwise ceiling
  function niceNum(range: number, round: boolean): number {
    const exponent = Math.floor(Math.log10(range));
    const fraction = range / Math.pow(10, exponent);
    let niceFraction: number;

    if (round) {
      if (fraction < 1.5) niceFraction = 1;
      else if (fraction < 3) niceFraction = 2;
      else if (fraction < 7) niceFraction = 5;
      else niceFraction = 10;
    } else {
      if (fraction <= 1) niceFraction = 1;
      else if (fraction <= 2) niceFraction = 2;
      else if (fraction <= 5) niceFraction = 5;
      else niceFraction = 10;
    }

    return niceFraction * Math.pow(10, exponent);
  }

  // Generate nice tick values using Heckbert's algorithm
  function getNiceTicks(min: number, max: number, maxTicks: number = 8): number[] {
    if (max === min) return [min];
    
    const range = niceNum(max - min, false);
    const tickSpacing = niceNum(range / (maxTicks - 1), true);
    const niceLowerBound = Math.floor(min / tickSpacing) * tickSpacing;
    const niceUpperBound = Math.ceil(max / tickSpacing) * tickSpacing;
    
    const ticks: number[] = [];
    for (let tick = niceLowerBound; tick <= niceUpperBound + tickSpacing * 0.5; tick += tickSpacing) {
      // Round to avoid floating point issues
      const roundedTick = Math.round(tick * 1e10) / 1e10;
      if (roundedTick >= min - tickSpacing * 0.1 && roundedTick <= max + tickSpacing * 0.1) {
        ticks.push(roundedTick);
      }
    }
    return ticks;
  }

  // For time, use nice intervals that make sense (30s, 1m, 2m, 5m, 10m, etc.)
  function getNiceTimeTicks(maxSeconds: number, maxTicks: number = 10): number[] {
    // Nice time intervals in seconds - more granular options
    const niceIntervals = [10, 15, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600];
    const idealInterval = maxSeconds / maxTicks;
    const interval = niceIntervals.find(i => i >= idealInterval) || niceIntervals[niceIntervals.length - 1];
    
    const ticks: number[] = [];
    for (let t = 0; t <= maxSeconds; t += interval) {
      ticks.push(t);
    }
    return ticks;
  }

  function getChartData(chart: ChartConfig) {
    const mode = axisModes[chart.key];
    if (mode === "distance") {
      const resampled = resampleByDistance(records);
      const data: ChartDataPoint[] = resampled.map((r, i) => ({
        distance_m: r.distance_m,
        elapsed: i,
        speed_mps: r.speed_mps,
        hr_bpm: r.hr_bpm,
        power_w: r.power_w,
        altitude_m: r.altitude_m,
      }));
      const maxDistance = Math.max(...data.map(d => d.distance_m));
      return {
        data,
        xKey: "distance_m" as const,
        xLabel: "Distance",
        tickFormatter: formatDistanceAxis,
        ticks: getNiceTicks(0, maxDistance, 10),
      };
    }
    const data: ChartDataPoint[] = timestamps.map((ts, i) => ({
      distance_m: records[i].distance_m,
      elapsed: ts - firstTs,
      speed_mps: records[i].speed_mps,
      hr_bpm: records[i].hr_bpm,
      power_w: records[i].power_w,
      altitude_m: records[i].altitude_m,
    }));
    const maxTime = Math.max(...data.map(d => d.elapsed));
    return {
      data,
      xKey: "elapsed" as const,
      xLabel: "Time",
      tickFormatter: formatElapsedTime,
      ticks: getNiceTimeTicks(maxTime, 10),
    };
  }

  const otherPositions: [number, number][] | null = comparison?.other_geojson
    ? comparison.other_geojson.features
        .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
        .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]])
    : null;

  const gapSeries = comparison?.gap_series ?? [];
  const coloredSegments = comparison?.comparable
    ? buildColoredSegments(gapSeries, posByDist)
    : [];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={onBack}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            &larr; Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Activity Details
          </h1>
        </div>

        {/* Stats Grid - Row 1: Ride Basics */}
        <div className="mb-3">
          <h2 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Ride Basics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatTile label="Date" value={new Date(activity.started_at).toLocaleDateString()} />
            <StatTile label="Distance" value={formatDistance(activity.total_distance_m, unitSystem)} />
            <StatTile label="Duration" value={formatTime(activity.moving_time_s)} />
            <StatTile label="Elevation" value={formatElevation(activity.elevation_gain_m, unitSystem)} />
            <StatTile label="Avg Speed" value={formatSpeed(activity.avg_speed_mps, unitSystem)} />
            <StatTile label="Avg HR" value={activity.avg_hr_bpm ? `${activity.avg_hr_bpm} bpm` : "—"} />
          </div>
        </div>

        {/* Stats Grid - Row 2: Training Metrics */}
        <div className="mb-6">
          <h2 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Training Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatTile 
              label="Avg Power" 
              value={activity.avg_power_w ? `${activity.avg_power_w} W` : "—"} 
              subtitle={activity.power_source === "hr_derived" ? "HR-derived" : undefined}
            />
            <StatTile label="NP" value={activity.np_power_w ? `${activity.np_power_w} W` : "—"} />
            <StatTile label="IF" value={activity.intensity_factor ? activity.intensity_factor.toFixed(2) : "—"} />
            <StatTile label="TSS" value={activity.tss ? Math.round(activity.tss).toString() : "—"} />
            <StatTile 
              label="W'bal Min" 
              value={activity.wbal_min_pct != null ? `${Math.round(activity.wbal_min_pct)}%` : "—"} 
            />
            <StatTile label="Max HR" value={activity.max_hr_bpm ? `${activity.max_hr_bpm} bpm` : "—"} />
          </div>
        </div>

        {/* Zone Distribution Charts */}
        {(activity.power_zone_times || activity.hr_zone_times) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {activity.power_zone_times && (
              <ZoneChart 
                title="Power Zones" 
                zoneTimes={activity.power_zone_times} 
                zoneColors={POWER_ZONE_COLORS}
              />
            )}
            {activity.hr_zone_times && (
              <ZoneChart 
                title="HR Zones" 
                zoneTimes={activity.hr_zone_times} 
                zoneColors={HR_ZONE_COLORS}
              />
            )}
          </div>
        )}

        {/* Compare selector */}
        {sameRoute && sameRoute.route_id !== null && sameRoute.activities.length > 0 && (
          <div className="mb-6 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Compare with another ride on this route
            </label>
            <select
              value={compareOtherId ?? ""}
              onChange={(e) => setCompareOtherId(e.target.value ? Number(e.target.value) : null)}
              className="w-full sm:w-auto px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select a ride...</option>
              {sameRoute.activities.map((a) => (
                <option key={a.id} value={a.id}>
                  {new Date(a.started_at).toLocaleDateString()} — {formatDistance(a.total_distance_m, unitSystem)}
                </option>
              ))}
            </select>
          </div>
        )}

        {comparison && !comparison.comparable && (
          <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-400">
            These rides are not on the same route and cannot be compared.
          </div>
        )}

        {/* Map */}
        {positions.length > 0 && (
          <div className="mb-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <MapContainer
              center={center}
              zoom={13}
              style={{ height: "400px", width: "100%" }}
            >
              <TileLayer
                url="/tiles/{z}/{x}/{y}.png"
                attribution='&copy; OpenStreetMap'
              />
              <FitBounds positions={positions} />
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
          </div>
        )}

        {/* Gap Chart (comparison mode) */}
        {comparison && comparison.comparable && gapSeries.length > 0 && (
          <ChartCard title="Time Gap" subtitle="vs comparison ride">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={gapSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="distance_m"
                  tickFormatter={(v) => formatDistance(v, unitSystem)}
                  tick={{ fontSize: 12, fill: "#6b7280" }}
                  axisLine={{ stroke: "#d1d5db" }}
                  tickLine={{ stroke: "#d1d5db" }}
                />
                <YAxis
                  tick={{ fontSize: 12, fill: "#6b7280" }}
                  axisLine={{ stroke: "#d1d5db" }}
                  tickLine={{ stroke: "#d1d5db" }}
                  label={{ value: "Gap (s)", angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "white",
                    border: "1px solid #e5e7eb",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                />
                <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                <Line
                  type="monotone"
                  dataKey="gap_s"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                  name="Time Gap"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        )}

        {/* Data Charts */}
        {CHARTS.map((chart) => {
          const { data, xKey, tickFormatter, ticks } = getChartData(chart);
          const hasData = data.some((d) => d[chart.dataKey as keyof typeof d] !== null);
          if (!hasData) return null;
          
          // Calculate Y-axis domain with margin
          const values = data
            .map((d) => d[chart.dataKey as keyof typeof d] as number | null)
            .filter((v): v is number => v !== null);
          const minVal = Math.min(...values);
          const maxVal = Math.max(...values);
          const range = maxVal - minVal;
          const margin = range * 0.1 || 5; // 10% margin, minimum 5
          const yMin = Math.max(0, Math.floor(minVal - margin));
          const yMax = Math.ceil(maxVal + margin);
          
          return (
            <ChartCard
              key={chart.key}
              title={chart.label}
              action={
                <button
                  onClick={() => toggleAxis(chart.key)}
                  className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                    axisModes[chart.key] === "distance"
                      ? "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300"
                      : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
                  }`}
                >
                  {axisModes[chart.key] === "distance" ? "Distance" : "Time"}
                </button>
              }
            >
              <ResponsiveContainer width="100%" height={200}>
                <LineChart 
                  data={data}
                  onMouseLeave={handleChartLeave}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey={xKey}
                    type="number"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={tickFormatter}
                    ticks={ticks}
                    interval={0}
                    tick={{ fontSize: 10, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                  />
                  <YAxis
                    domain={[yMin, yMax]}
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                    label={{ value: chart.unit, angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      // Update map marker when tooltip is active
                      if (active && payload?.[0]?.payload) {
                        const p = payload[0].payload;
                        const mode = axisModes[chart.key];
                        const pos = mode === "distance"
                          ? findPositionByDistance(p.distance_m)
                          : findPositionByElapsed(p.elapsed);
                        if (pos) {
                          setTimeout(() => setHoveredPosition(pos), 0);
                        }
                      }
                      // Render default-style tooltip
                      if (!active || !payload?.length) return null;
                      const value = payload[0].value;
                      return (
                        <div style={{
                          backgroundColor: "white",
                          border: "1px solid #e5e7eb",
                          borderRadius: "8px",
                          padding: "8px 12px",
                          fontSize: "12px",
                        }}>
                          {chart.label}: {typeof value === "number" ? value.toFixed(2) : value}
                        </div>
                      );
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey={chart.dataKey}
                    stroke={chart.color}
                    strokeWidth={2}
                    dot={false}
                    name={chart.label}
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          );
        })}

        {/* W'bal Chart */}
        {wbalData && wbalData.wbal_series.length > 0 && (
          <WbalChart 
            wbalData={wbalData} 
            findPositionByElapsed={findPositionByElapsed}
            setHoveredPosition={setHoveredPosition}
          />
        )}
      </div>
    </div>
  );
}

function StatTile({ label, value, subtitle }: { label: string; value: string; subtitle?: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className="text-lg font-semibold text-gray-900 dark:text-white tabular-nums">
        {value}
      </div>
      {subtitle && (
        <div className="text-xs text-indigo-500 dark:text-indigo-400 mt-0.5">
          {subtitle}
        </div>
      )}
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
          {subtitle && (
            <p className="text-xs text-gray-500 dark:text-gray-400">{subtitle}</p>
          )}
        </div>
        {action}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}



function ZoneChart({ 
  title, 
  zoneTimes, 
  zoneColors 
}: { 
  title: string; 
  zoneTimes: Record<string, number>; 
  zoneColors: Record<string, string>;
}) {
  // Convert zone times to array and calculate percentages
  const zones = Object.entries(zoneTimes)
    .map(([zone, seconds]) => ({
      zone,
      seconds,
      label: `Z${zone}`,
    }))
    .sort((a, b) => parseInt(a.zone) - parseInt(b.zone));

  const totalSeconds = zones.reduce((sum, z) => sum + z.seconds, 0);
  
  if (totalSeconds === 0) return null;

  const formatZoneTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">{title}</h3>
      <div className="space-y-2">
        {zones.map(({ zone, seconds, label }) => {
          const percentage = (seconds / totalSeconds) * 100;
          const color = zoneColors[zone] || "#6b7280";
          
          return (
            <div key={zone} className="flex items-center gap-3">
              <div className="w-8 text-xs font-medium text-gray-600 dark:text-gray-400">
                {label}
              </div>
              <div className="flex-1 h-6 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ 
                    width: `${Math.max(percentage, 1)}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <div className="w-16 text-xs text-right text-gray-600 dark:text-gray-400 tabular-nums">
                {formatZoneTime(seconds)}
              </div>
              <div className="w-12 text-xs text-right text-gray-500 dark:text-gray-500 tabular-nums">
                {percentage.toFixed(0)}%
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-between text-xs text-gray-500 dark:text-gray-400">
        <span>Total</span>
        <span className="tabular-nums">{formatZoneTime(totalSeconds)}</span>
      </div>
    </div>
  );
}



function WbalChart({ 
  wbalData, 
  findPositionByElapsed,
  setHoveredPosition,
}: { 
  wbalData: WbalResponse;
  findPositionByElapsed: (elapsed: number) => [number, number] | null;
  setHoveredPosition: (pos: [number, number] | null) => void;
}) {
  const { wbal_series, w_prime_joules, wbal_min_pct } = wbalData;
  
  if (!w_prime_joules || wbal_series.length === 0) return null;

  // Find minimum point
  const minPoint = wbal_series.reduce((min, point) => 
    point.wbal_pct < min.wbal_pct ? point : min
  , wbal_series[0]);

  // Color function for W'bal level
  const getWbalColor = (pct: number): string => {
    if (pct > 50) return "#22c55e"; // Green
    if (pct > 25) return "#eab308"; // Yellow
    return "#ef4444"; // Red
  };

  const formatElapsedTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Generate nice time ticks
  const maxTime = Math.max(...wbal_series.map(d => d.elapsed_s));
  const niceIntervals = [30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600];
  const idealInterval = maxTime / 10;
  const interval = niceIntervals.find(i => i >= idealInterval) || niceIntervals[niceIntervals.length - 1];
  const ticks: number[] = [];
  for (let t = 0; t <= maxTime; t += interval) {
    ticks.push(t);
  }

  return (
    <ChartCard 
      title="W'bal" 
      subtitle={`W' = ${Math.round(w_prime_joules / 1000)} kJ • Min: ${wbal_min_pct?.toFixed(0) ?? "—"}%`}
    >
      <ResponsiveContainer width="100%" height={200}>
        <LineChart 
          data={wbal_series}
          onMouseLeave={() => setHoveredPosition(null)}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          
          {/* Color bands for depletion zones */}
          <ReferenceArea y1={0} y2={25} fill="#fee2e2" fillOpacity={0.5} />
          <ReferenceArea y1={25} y2={50} fill="#fef9c3" fillOpacity={0.5} />
          <ReferenceArea y1={50} y2={100} fill="#dcfce7" fillOpacity={0.5} />
          
          <XAxis
            dataKey="elapsed_s"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={formatElapsedTime}
            ticks={ticks}
            interval={0}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickLine={{ stroke: "#d1d5db" }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickLine={{ stroke: "#d1d5db" }}
            label={{ value: "%", angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload?.[0]?.payload) {
                const p = payload[0].payload;
                const pos = findPositionByElapsed(p.elapsed_s);
                if (pos) {
                  setTimeout(() => setHoveredPosition(pos), 0);
                }
              }
              if (!active || !payload?.length) return null;
              const point = payload[0].payload;
              return (
                <div style={{
                  backgroundColor: "white",
                  border: "1px solid #e5e7eb",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "12px",
                }}>
                  <div>W'bal: {point.wbal_pct.toFixed(0)}%</div>
                  <div style={{ color: "#6b7280" }}>
                    {(point.wbal_joules / 1000).toFixed(1)} kJ
                  </div>
                </div>
              );
            }}
          />
          
          {/* Threshold lines */}
          <ReferenceLine y={50} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.5} />
          <ReferenceLine y={25} stroke="#ef4444" strokeDasharray="3 3" strokeOpacity={0.5} />
          
          <Line
            type="monotone"
            dataKey="wbal_pct"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            name="W'bal"
          />
          
          {/* Minimum point marker */}
          <ReferenceDot
            x={minPoint.elapsed_s}
            y={minPoint.wbal_pct}
            r={6}
            fill={getWbalColor(minPoint.wbal_pct)}
            stroke="#fff"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
