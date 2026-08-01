import { useState, useEffect } from "react";
import type { Activity } from "./api";
import { ApiError, fetchActivities, login, uploadFit, fetchJobStatus } from "./api";
import { formatDistance, formatTime, formatDate } from "./format";
import { ErrorDisplay } from "./ErrorDisplay";

export function ActivityList({
  onSelect,
}: {
  onSelect: (id: number) => void;
}) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchActivities()
      .then(setActivities)
      .catch((e) => setError(e));
  }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadFit(file);
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
              const updated = await fetchActivities();
              setActivities(updated);
              break;
            }
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
      setError(err as Error);
    } finally {
      setUploading(false);
    }
  }

  if (error) {
    return <ErrorDisplay error={error} context="loading activities" />;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Fitter
        </h1>
        <div className="flex items-center gap-3">
          <label className="relative cursor-pointer">
            <input
              type="file"
              accept=".fit"
              onChange={handleUpload}
              disabled={uploading || processing}
              className="sr-only"
            />
            <span className={`inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
              uploading || processing
                ? "bg-gray-100 dark:bg-gray-700 text-gray-400 cursor-not-allowed"
                : "bg-indigo-600 text-white hover:bg-indigo-700"
            }`}>
              {uploading ? "Uploading..." : processing ? "Processing..." : "Upload FIT"}
            </span>
          </label>
        </div>
      </div>

      {activities.length === 0 ? (
        <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <p className="text-gray-500 dark:text-gray-400">
            No activities yet. Upload a FIT file to get started.
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-900/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Distance
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Moving Time
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                  Elevation
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {activities.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => onSelect(a.id)}
                  className="hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                    {formatDate(a.started_at)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right tabular-nums">
                    {formatDistance(a.total_distance_m)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right tabular-nums">
                    {formatTime(a.moving_time_s)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right tabular-nums">
                    {a.elevation_gain_m.toFixed(0)} m
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function Login({
  onLogin,
}: {
  onLogin: (isAdmin: boolean) => void;
}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const result = await login(username, password);
    if (result) {
      onLogin(result.is_admin ?? false);
    } else {
      setError("Invalid credentials");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <div className="w-full max-w-sm">
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-8">
          <h1 className="text-2xl font-bold text-center text-gray-900 dark:text-white mb-6">
            Fitter
          </h1>
          
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="Enter username"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="Enter password"
              />
            </div>
            
            <button
              type="submit"
              className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Sign in
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
