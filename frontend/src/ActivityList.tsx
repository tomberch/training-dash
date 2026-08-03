import { useState, useEffect } from "react";
import type { Activity } from "./api";
import { ApiError, fetchActivities, login } from "./api";
import { formatDistance, formatTime, formatDate, formatElevation } from "./format";
import type { UnitSystem } from "./format";
import { ErrorDisplay } from "./ErrorDisplay";

export function ActivityList({
  onSelect,
  unitSystem = "metric",
}: {
  onSelect: (id: number) => void;
  unitSystem?: UnitSystem;
}) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<Error | ApiError | null>(null);

  useEffect(() => {
    fetchActivities()
      .then(setActivities)
      .catch((e) => setError(e));
  }, []);

  if (error) {
    return <ErrorDisplay error={error} context="loading activities" />;
  }

  return (
    <div>
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
                  Activity
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
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {a.title || formatDate(a.started_at)}
                      </span>
                      {a.title_source === "pending" && (
                        <span title="Click to generate location-based title">
                          <svg className="w-3.5 h-3.5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                        </span>
                      )}
                    </div>
                    {a.title && (
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {formatDate(a.started_at)}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right tabular-nums">
                    {formatDistance(a.total_distance_m, unitSystem)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right tabular-nums">
                    {formatTime(a.moving_time_s)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 text-right tabular-nums">
                    {formatElevation(a.elevation_gain_m, unitSystem)}
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
            TrainingDash
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
