import { useState, useEffect, useMemo } from "react";
import { MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
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
} from "recharts";
import type { Activity, GeoJSONFeatureCollection, CompareResponse, SameRouteResponse, GapPoint } from "./api";
import { fetchActivity, fetchActivityRecords, fetchSameRouteActivities, fetchComparison } from "./api";
import { formatDistance, formatTime } from "./format";
import { resampleByDistance } from "./resampler";
import type { FitRecord } from "./resampler";

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

// Component to fit map bounds to polyline
function FitBounds({ positions }: { positions: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (positions.length > 0) {
      const bounds: LatLngBounds = L.latLngBounds(positions.map(p => L.latLng(p[0], p[1])));
      map.fitBounds(bounds, { padding: [20, 20] });
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

interface Props {
  activityId: number;
  onBack: () => void;
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

export function ActivityDetail({ activityId, onBack }: Props) {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [axisModes, setAxisModes] = useState<{ [key: string]: AxisMode }>({
    speed: "time",
    hr: "time",
    power: "time",
    elevation: "time",
  });
  const [sameRoute, setSameRoute] = useState<SameRouteResponse | null>(null);
  const [compareOtherId, setCompareOtherId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);

  useEffect(() => {
    setComparison(null);
    setCompareOtherId(null);
    Promise.all([
      fetchActivity(activityId),
      fetchActivityRecords(activityId),
      fetchSameRouteActivities(activityId),
    ])
      .then(([a, g, sr]) => {
        setActivity(a);
        setGeojson(g);
        setSameRoute(sr);
      })
      .catch((e) => setError(e.message));
  }, [activityId]);

  useEffect(() => {
    if (compareOtherId === null) {
      setComparison(null);
      return;
    }
    fetchComparison(activityId, compareOtherId)
      .then(setComparison)
      .catch((e) => setError(e.message));
  }, [activityId, compareOtherId]);

  const records = useMemo(() => (geojson ? geojsonToRecords(geojson) : []), [geojson]);
  const timestamps = useMemo(() => (geojson ? geojsonToTimestamps(geojson) : []), [geojson]);
  const posByDist = useMemo(() => (geojson ? positionsByDistance(geojson.features) : []), [geojson]);
  const firstTs = timestamps.length > 0 ? timestamps[0] : 0;

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
        <div className="max-w-6xl mx-auto">
          <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400">
            Error: {error}
          </div>
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
      return {
        data,
        xKey: "distance_m" as const,
        xLabel: "Distance (m)",
        tickFormatter: (v: number) => formatDistance(v),
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
    return {
      data,
      xKey: "elapsed" as const,
      xLabel: "Time (s)",
      tickFormatter: (v: number) => `${v.toFixed(0)}`,
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

        {/* Stats Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3 mb-6">
          <StatTile label="Date" value={new Date(activity.started_at).toLocaleDateString()} />
          <StatTile label="Distance" value={formatDistance(activity.total_distance_m)} />
          <StatTile label="Moving Time" value={formatTime(activity.moving_time_s)} />
          <StatTile label="Elevation" value={`${activity.elevation_gain_m.toFixed(0)} m`} />
          <StatTile label="Avg Speed" value={`${activity.avg_speed_mps.toFixed(1)} m/s`} />
          {activity.avg_hr_bpm && <StatTile label="Avg HR" value={`${activity.avg_hr_bpm} bpm`} />}
          {activity.avg_power_w && <StatTile label="Avg Power" value={`${activity.avg_power_w} W`} />}
        </div>

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
                  {new Date(a.started_at).toLocaleDateString()} — {formatDistance(a.total_distance_m)}
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
              className="h-80 md:h-96"
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; OpenStreetMap'
              />
              <FitBounds positions={positions} />
              {coloredSegments.length > 0
                ? coloredSegments.map((seg, i) => (
                    <Polyline key={i} positions={seg.positions} color={seg.color} weight={4} />
                  ))
                : <Polyline positions={positions} color="#6366f1" weight={3} />}
              {otherPositions && (
                <Polyline positions={otherPositions} color="#f59e0b" weight={3} dashArray="5,5" />
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
                  tickFormatter={(v) => formatDistance(v)}
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
          const { data, xKey, tickFormatter } = getChartData(chart);
          const hasData = data.some((d) => d[chart.dataKey as keyof typeof d] !== null);
          if (!hasData) return null;
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
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey={xKey}
                    tickFormatter={tickFormatter}
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                    label={{ value: chart.unit, angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "white",
                      border: "1px solid #e5e7eb",
                      borderRadius: "8px",
                      fontSize: "12px",
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
      </div>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className="text-lg font-semibold text-gray-900 dark:text-white tabular-nums">
        {value}
      </div>
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
