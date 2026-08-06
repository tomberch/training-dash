import { useState, useEffect, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import type { PeakPower, PowerCurvePoint } from "../api";
import { fetchPowerCurve } from "../api";

// Key durations to highlight (in seconds)
const KEY_DURATIONS = [5, 30, 60, 300, 1200, 3600];

// Tooltip styles (extracted for consistency)
const TOOLTIP_STYLE = {
  container: {
    backgroundColor: "white",
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    padding: "8px 12px",
    fontSize: "12px",
  },
  prTitle: "#d97706",
  normalTitle: "#111827",
  activityColor: "#f59e0b",
  allTimeColor: "#6366f1",
  secondaryText: "#6b7280",
} as const;

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h${m}m` : `${h}h`;
}

interface ActivityPowerCurveProps {
  peaks: PeakPower[];
  showAllTimeCurve?: boolean;
}

export function ActivityPowerCurve({ peaks, showAllTimeCurve: initialShowAllTime = true }: ActivityPowerCurveProps) {
  const [allTimeCurve, setAllTimeCurve] = useState<PowerCurvePoint[]>([]);
  const [showAllTime, setShowAllTime] = useState(initialShowAllTime);
  const [loading, setLoading] = useState(false);

  // Fetch all-time power curve when overlay is enabled
  useEffect(() => {
    if (showAllTime && allTimeCurve.length === 0) {
      setLoading(true);
      fetchPowerCurve()
        .then((data) => {
          setAllTimeCurve(data);
        })
        .catch((e) => {
          console.error("[ActivityPowerCurve] Failed to fetch all-time power curve:", e);
          // Don't show error UI - overlay is optional enhancement
        })
        .finally(() => setLoading(false));
    }
  }, [showAllTime, allTimeCurve.length]);

  // Build chart data with log-scale X positions
  const chartData = useMemo(() => {
    const allDurations = new Set<number>();
    peaks.forEach((p) => allDurations.add(p.duration_seconds));
    if (showAllTime) {
      allTimeCurve.forEach((p) => allDurations.add(p.duration_seconds));
    }

    const peakMap = new Map(peaks.map((p) => [p.duration_seconds, p]));
    const allTimeMap = new Map(allTimeCurve.map((p) => [p.duration_seconds, p]));

    return Array.from(allDurations)
      .sort((a, b) => a - b)
      .map((duration) => {
        const peak = peakMap.get(duration);
        const allTime = allTimeMap.get(duration);

        return {
          duration,
          logDuration: Math.log10(duration),
          activityWatts: peak?.watts ?? null,
          allTimeWatts: showAllTime ? (allTime?.watts ?? null) : null,
          isPr: peak?.is_pr ?? false,
          pctOfPr: peak?.pct_of_pr ?? null,
        };
      });
  }, [peaks, allTimeCurve, showAllTime]);

  // Get PR points for highlighting
  const prPoints = useMemo(() => {
    return chartData.filter((d) => d.isPr && d.activityWatts !== null);
  }, [chartData]);

  // Get key duration labels for X-axis
  const keyDurationTicks = useMemo(() => {
    return KEY_DURATIONS.filter((d) => {
      const minDuration = Math.min(...peaks.map((p) => p.duration_seconds));
      const maxDuration = Math.max(...peaks.map((p) => p.duration_seconds));
      return d >= minDuration && d <= maxDuration;
    }).map((d) => Math.log10(d));
  }, [peaks]);

  if (peaks.length === 0) {
    return null;
  }

  // Count PRs
  const prCount = peaks.filter((p) => p.is_pr).length;

  return (
    <div className="mb-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            Power Curve
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {prCount > 0 ? (
              <span className="text-amber-600 dark:text-amber-400">
                {prCount} PR{prCount > 1 ? "s" : ""} set!
              </span>
            ) : (
              "Best efforts this ride"
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={showAllTime}
              onChange={(e) => setShowAllTime(e.target.checked)}
              className="rounded border-gray-300 dark:border-gray-600 text-indigo-600 focus:ring-indigo-500"
            />
            <span>Show all-time curve</span>
            {loading && (
              <span className="text-muted-foreground">Loading...</span>
            )}
          </label>
        </div>
      </div>

      <div className="p-4">
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="logDuration"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => formatDuration(Math.pow(10, v))}
              ticks={keyDurationTicks}
              tick={{ fontSize: 11, fill: "#6b7280" }}
              axisLine={{ stroke: "#d1d5db" }}
              tickLine={{ stroke: "#d1d5db" }}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 12, fill: "#6b7280" }}
              axisLine={{ stroke: "#d1d5db" }}
              tickLine={{ stroke: "#d1d5db" }}
              label={{
                value: "W",
                angle: -90,
                position: "insideLeft",
                fontSize: 12,
                fill: "#6b7280",
              }}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const data = payload[0].payload;
                return (
                  <div style={TOOLTIP_STYLE.container}>
                    <div
                      style={{
                        fontWeight: 600,
                        marginBottom: 4,
                        color: data.isPr ? TOOLTIP_STYLE.prTitle : TOOLTIP_STYLE.normalTitle,
                      }}
                    >
                      {formatDuration(data.duration)}
                      {data.isPr && " - PR!"}
                    </div>
                    {data.activityWatts !== null && (
                      <div style={{ color: TOOLTIP_STYLE.activityColor }}>
                        This ride: {data.activityWatts}W
                      </div>
                    )}
                    {data.allTimeWatts !== null && (
                      <div style={{ color: TOOLTIP_STYLE.allTimeColor }}>
                        All-time: {data.allTimeWatts}W
                      </div>
                    )}
                    {data.pctOfPr !== null && !data.isPr && (
                      <div style={{ color: TOOLTIP_STYLE.secondaryText }}>
                        {data.pctOfPr.toFixed(0)}% of PR
                      </div>
                    )}
                  </div>
                );
              }}
            />

            {/* All-time curve (background) */}
            {showAllTime && (
              <Line
                type="monotone"
                dataKey="allTimeWatts"
                stroke="#6366f1"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                name="All-time"
                connectNulls
              />
            )}

            {/* Activity curve (foreground) */}
            <Line
              type="monotone"
              dataKey="activityWatts"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              name="This ride"
              connectNulls
            />

            {/* PR markers */}
            {prPoints.map((pr) => (
              <ReferenceDot
                key={pr.duration}
                x={pr.logDuration}
                y={pr.activityWatts!}
                r={6}
                fill="#f59e0b"
                stroke="#fff"
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 mt-3 text-xs text-gray-500 dark:text-gray-400">
          <div className="flex items-center gap-2">
            <div className="w-4 h-0.5 bg-amber-500" />
            <span>This ride</span>
          </div>
          {showAllTime && (
            <div className="flex items-center gap-2">
              <div
                className="w-4 h-0.5 bg-indigo-500"
                style={{
                  backgroundImage:
                    "linear-gradient(90deg, #6366f1 50%, transparent 50%)",
                  backgroundSize: "6px 100%",
                }}
              />
              <span>All-time best</span>
            </div>
          )}
          {prCount > 0 && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-amber-500 border-2 border-white" />
              <span>PR</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
