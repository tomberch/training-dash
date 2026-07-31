import { useState, useEffect, useMemo } from "react";
import { MapContainer, Polyline, TileLayer } from "react-leaflet";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { Activity, GeoJSONFeatureCollection } from "./api";
import { fetchActivity, fetchActivityRecords } from "./api";
import { formatDistance, formatTime } from "./format";
import { resampleByDistance } from "./resampler";
import type { FitRecord } from "./resampler";

type AxisMode = "time" | "distance";

interface ChartConfig {
  key: string;
  label: string;
  unit: string;
  color: string;
  dataKey: string;
}

const CHARTS: ChartConfig[] = [
  { key: "speed", label: "Speed", unit: "m/s", color: "#8884d8", dataKey: "speed_mps" },
  { key: "hr", label: "Heart Rate", unit: "bpm", color: "#e84a5f", dataKey: "hr_bpm" },
  { key: "power", label: "Power", unit: "W", color: "#f6a623", dataKey: "power_w" },
  { key: "elevation", label: "Elevation", unit: "m", color: "#48b366", dataKey: "altitude_m" },
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

  useEffect(() => {
    Promise.all([
      fetchActivity(activityId),
      fetchActivityRecords(activityId),
    ])
      .then(([a, g]) => {
        setActivity(a);
        setGeojson(g);
      })
      .catch((e) => setError(e.message));
  }, [activityId]);

  const records = useMemo(() => (geojson ? geojsonToRecords(geojson) : []), [geojson]);
  const timestamps = useMemo(() => (geojson ? geojsonToTimestamps(geojson) : []), [geojson]);
  const firstTs = timestamps.length > 0 ? timestamps[0] : 0;

  if (error) return <div>Error: {error}</div>;
  if (!activity || !geojson) return <div>Loading...</div>;

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

  return (
    <div>
      <button onClick={onBack}>Back</button>
      <h1>Activity {activity.id}</h1>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        <StatTile label="Date" value={new Date(activity.started_at).toLocaleDateString()} />
        <StatTile label="Distance" value={formatDistance(activity.total_distance_m)} />
        <StatTile label="Moving Time" value={formatTime(activity.moving_time_s)} />
        <StatTile label="Elevation" value={`${activity.elevation_gain_m.toFixed(0)} m`} />
        <StatTile label="Avg Speed" value={`${activity.avg_speed_mps.toFixed(1)} m/s`} />
        {activity.avg_hr_bpm && <StatTile label="Avg HR" value={`${activity.avg_hr_bpm} bpm`} />}
        {activity.avg_power_w && <StatTile label="Avg Power" value={`${activity.avg_power_w} W`} />}
      </div>

      {positions.length > 0 && (
        <MapContainer
          center={center}
          zoom={13}
          style={{ height: "400px", marginBottom: "1rem" }}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap'
          />
          <Polyline positions={positions} color="blue" weight={3} />
        </MapContainer>
      )}

      {CHARTS.map((chart) => {
        const { data, xKey, xLabel, tickFormatter } = getChartData(chart);
        const hasData = data.some((d) => d[chart.dataKey as keyof typeof d] !== null);
        if (!hasData) return null;
        return (
          <div key={chart.key}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <h2>{chart.label}</h2>
              <button
                onClick={() => toggleAxis(chart.key)}
                style={{ fontSize: "0.75rem", padding: "0.15rem 0.5rem" }}
              >
                Axis: {axisModes[chart.key]}
              </button>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey={xKey}
                  tickFormatter={tickFormatter}
                  label={{ value: xLabel, position: "bottom" }}
                  type="number"
                  domain={["dataMin", "dataMax"]}
                />
                <YAxis label={{ value: chart.unit, angle: -90, position: "insideLeft" }} />
                <Tooltip />
                <Line type="monotone" dataKey={chart.dataKey} stroke={chart.color} dot={false} name={chart.label} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        );
      })}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        padding: "0.5rem 1rem",
        background: "#f0f0f0",
        borderRadius: "4px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: "0.75rem", color: "#666" }}>{label}</div>
      <div style={{ fontSize: "1.1rem", fontWeight: "bold" }}>{value}</div>
    </div>
  );
}