import { useState, useEffect } from "react";
import type { Activity } from "./api";
import { fetchActivities, login, uploadFit } from "./api";

function formatDistance(m: number): string {
  return `${(m / 1000).toFixed(1)} km`;
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${sec}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CH", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function ActivityList({
  onSelect,
}: {
  onSelect: (id: number) => void;
}) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchActivities()
      .then(setActivities)
      .catch((e) => setError(e.message));
  }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadFit(file);
      const updated = await fetchActivities();
      setActivities(updated);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h1>Fitter</h1>
      <div style={{ marginBottom: "1rem" }}>
        <input
          type="file"
          accept=".fit"
          onChange={handleUpload}
          disabled={uploading}
        />
        {uploading && <span> Uploading...</span>}
      </div>
      {activities.length === 0 ? (
        <p>No activities yet. Upload a FIT file to get started.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Date</th>
              <th style={{ textAlign: "right" }}>Distance</th>
              <th style={{ textAlign: "right" }}>Moving Time</th>
              <th style={{ textAlign: "right" }}>Elevation</th>
            </tr>
          </thead>
          <tbody>
            {activities.map((a) => (
              <tr
                key={a.id}
                onClick={() => onSelect(a.id)}
                style={{ cursor: "pointer" }}
              >
                <td>{formatDate(a.started_at)}</td>
                <td style={{ textAlign: "right" }}>
                  {formatDistance(a.total_distance_m)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {formatTime(a.moving_time_s)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {a.elevation_gain_m.toFixed(0)} m
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function Login({
  onLogin,
}: {
  onLogin: () => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ok = await login(username, password);
    if (ok) {
      onLogin();
    } else {
      setError("Invalid credentials");
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>Fitter Login</h1>
      {error && <p style={{ color: "red" }}>{error}</p>}
      <div>
        <label>
          Username:{" "}
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
      </div>
      <div>
        <label>
          Password:{" "}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
      </div>
      <button type="submit">Login</button>
    </form>
  );
}