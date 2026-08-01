import { useState, useEffect } from "react";
import type { Activity } from "./api";
import { fetchActivities, login, uploadFit, fetchJobStatus } from "./api";
import { formatDistance, formatTime, formatDate } from "./format";

export function ActivityList({
  onSelect,
}: {
  onSelect: (id: number) => void;
}) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);

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
      const result = await uploadFit(file);
      // If upload returned 202 (async), poll job status until complete
      if ("job_id" in result && result.job_id) {
        setProcessing(true);
        const jobId = result.job_id;
        const maxPolls = 30;
        for (let i = 0; i < maxPolls; i++) {
          await new Promise((r) => setTimeout(r, 2000));
          try {
            const status = await fetchJobStatus(jobId);
            if (status.status === "complete") {
              const updated = await fetchActivities();
              setActivities(updated);
              break;
            } else if (status.status === "not_found") {
              // Job disappeared, refresh activities anyway
              const updated = await fetchActivities();
              setActivities(updated);
              break;
            }
            // Still pending/processing, continue polling
          } catch {
            // Error checking status, keep polling
          }
        }
        setProcessing(false);
      } else {
        const updated = await fetchActivities();
        setActivities(updated);
      }
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
        {processing && <span> Processing...</span>}
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