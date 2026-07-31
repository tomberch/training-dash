import { useState, useEffect } from "react";
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
import type { Activity, ActivityRecord } from "./api";
import { fetchActivity, fetchActivityRecords } from "./api";

function formatDistance(m: number): string {
  return `${(m / 1000).toFixed(1)} km`;
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

interface Props {
  activityId: number;
  onBack: () => void;
}

export function ActivityDetail({ activityId, onBack }: Props) {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [records, setRecords] = useState<ActivityRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchActivity(activityId),
      fetchActivityRecords(activityId),
    ])
      .then(([a, r]) => {
        setActivity(a);
        setRecords(r.records);
      })
      .catch((e) => setError(e.message));
  }, [activityId]);

  if (error) return <div>Error: {error}</div>;
  if (!activity) return <div>Loading...</div>;

  const gpsRecords = records.filter((r) => r.lat !== null && r.lon !== null);
  const positions: [number, number][] = gpsRecords.map((r) => [r.lat!, r.lon!]);

  const chartData = records.map((r, i) => ({
    time: i,
    speed: r.speed_mps,
    distance: r.distance_m,
  }));

  const center: [number, number] =
    positions.length > 0 ? positions[0] : [47.3769, 8.5417];

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

      {chartData.length > 0 && (
        <div>
          <h2>Speed</h2>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" label={{ value: "Time (s)", position: "bottom" }} />
              <YAxis label={{ value: "Speed (m/s)", angle: -90, position: "insideLeft" }} />
              <Tooltip />
              <Line type="monotone" dataKey="speed" stroke="#8884d8" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
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