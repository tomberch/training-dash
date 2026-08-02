import { useState, useEffect, useMemo } from "react";
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
import type { PowerCurvePoint, FitnessResponse } from "../api";
import { fetchPowerCurve, fetchFitness, fetchMe } from "../api";

// Key durations to label (in seconds)
const KEY_DURATIONS = [5, 30, 60, 300, 1200, 3600, 7200];

// Standard durations for fitness model curve
const MODEL_DURATIONS = [1, 2, 5, 10, 15, 30, 60, 120, 180, 300, 600, 1200, 1800, 2400, 3600, 5400, 7200];

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return m > 0 ? `${h}h${m}m` : `${h}h`;
}

function getStalenessColor(daysAgo: number): string {
  if (daysAgo <= 30) return "#22c55e"; // Green
  if (daysAgo <= 90) return "#eab308"; // Yellow
  return "#ef4444"; // Red
}

function getStalenessLabel(daysAgo: number): string {
  if (daysAgo <= 30) return "Fresh";
  if (daysAgo <= 90) return "Aging";
  return "Stale";
}

interface DatePreset {
  label: string;
  days?: number;
  all?: boolean;
}

const DATE_PRESETS: DatePreset[] = [
  { label: "90 days", days: 90 },
  { label: "180 days", days: 180 },
  { label: "1 year", days: 365 },
  { label: "All time", all: true },
];

// Compute modeled power from 3-param CP model: P(t) = PP for t < W'/PP, else W'/t + CP
function modelPower(t: number, pp: number, wPrime: number, cp: number): number {
  const peakDuration = wPrime / (pp - cp);
  if (t <= peakDuration) return pp;
  return wPrime / t + cp;
}

export function PowerCurveView() {
  const [curveData, setCurveData] = useState<PowerCurvePoint[]>([]);
  const [comparisonData, setComparisonData] = useState<PowerCurvePoint[]>([]);
  const [fitness, setFitness] = useState<FitnessResponse | null>(null);
  const [userWeight, setUserWeight] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [activePreset, setActivePreset] = useState<number>(3); // Default: All time
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonPreset, setComparisonPreset] = useState<number>(0); // 90 days
  const [showWkg, setShowWkg] = useState(false);
  const [showModel, setShowModel] = useState(false);

  // Compute date range based on preset
  const getDateRange = (presetIdx: number): { start?: string; end?: string } => {
    const today = new Date();
    const endDate = today.toISOString().split("T")[0];
    const preset = DATE_PRESETS[presetIdx];
    
    if (preset.all) {
      return { start: undefined, end: endDate };
    }
    
    const startDate = new Date(today);
    startDate.setDate(startDate.getDate() - (preset.days || 365));
    return { start: startDate.toISOString().split("T")[0], end: endDate };
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    
    const mainRange = getDateRange(activePreset);
    
    const promises: Promise<unknown>[] = [
      fetchPowerCurve(mainRange.start, mainRange.end),
      fetchFitness(),
      fetchMe(),
    ];
    
    if (showComparison) {
      const compRange = getDateRange(comparisonPreset);
      promises.push(fetchPowerCurve(compRange.start, compRange.end));
    }
    
    Promise.all(promises)
      .then(([curve, fit, me, comp]) => {
        setCurveData(curve as PowerCurvePoint[]);
        setFitness(fit as FitnessResponse);
        setUserWeight((me as { weight_kg?: number }).weight_kg || null);
        if (comp) setComparisonData(comp as PowerCurvePoint[]);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message || "Failed to load power curve data");
        setLoading(false);
      });
  }, [activePreset, showComparison, comparisonPreset]);

  // Build chart data with log-scale X positions
  const chartData = useMemo(() => {
    const allDurations = new Set<number>();
    curveData.forEach(p => allDurations.add(p.duration_seconds));
    comparisonData.forEach(p => allDurations.add(p.duration_seconds));
    
    const mainMap = new Map(curveData.map(p => [p.duration_seconds, p]));
    const compMap = new Map(comparisonData.map(p => [p.duration_seconds, p]));
    
    const data = Array.from(allDurations).sort((a, b) => a - b).map(duration => {
      const main = mainMap.get(duration);
      const comp = compMap.get(duration);
      const weightFactor = showWkg && userWeight ? userWeight : 1;
      
      return {
        duration,
        logDuration: Math.log10(duration),
        watts: main ? main.watts : null,
        wkg: main && userWeight ? main.watts / weightFactor : null,
        compWatts: comp ? comp.watts : null,
        compWkg: comp && userWeight ? comp.watts / weightFactor : null,
        daysAgo: main?.days_ago,
        achievedDate: main?.achieved_date,
      };
    });
    
    return data;
  }, [curveData, comparisonData, showWkg, userWeight]);

  // Build fitness model curve
  const modelCurve = useMemo(() => {
    if (!showModel || !fitness?.current) return [];
    
    const { pp_watts, w_prime_joules, cp_watts } = fitness.current;
    const weightFactor = showWkg && userWeight ? userWeight : 1;
    
    return MODEL_DURATIONS.map(duration => ({
      duration,
      logDuration: Math.log10(duration),
      modelWatts: modelPower(duration, pp_watts, w_prime_joules, cp_watts),
      modelWkg: modelPower(duration, pp_watts, w_prime_joules, cp_watts) / weightFactor,
    }));
  }, [showModel, fitness, showWkg, userWeight]);

  // Merge model curve with main data for chart
  const mergedChartData = useMemo(() => {
    if (!showModel || modelCurve.length === 0) return chartData;
    
    const merged = [...chartData];
    const existingDurations = new Set(chartData.map(d => d.duration));
    
    modelCurve.forEach(m => {
      if (!existingDurations.has(m.duration)) {
        merged.push({
          duration: m.duration,
          logDuration: m.logDuration,
          watts: null,
          wkg: null,
          compWatts: null,
          compWkg: null,
          daysAgo: undefined,
          achievedDate: undefined,
        });
      }
    });
    
    merged.sort((a, b) => a.duration - b.duration);
    
    // Add model values
    const modelMap = new Map(modelCurve.map(m => [m.duration, m]));
    return merged.map(d => ({
      ...d,
      modelWatts: modelMap.get(d.duration)?.modelWatts || null,
      modelWkg: modelMap.get(d.duration)?.modelWkg || null,
    }));
  }, [chartData, modelCurve, showModel]);

  // Y-axis domain
  const yDomain = useMemo(() => {
    const values = mergedChartData.flatMap(d => [
      showWkg ? d.wkg : d.watts,
      showComparison ? (showWkg ? d.compWkg : d.compWatts) : null,
      showModel ? (showWkg ? (d as { modelWkg?: number }).modelWkg : (d as { modelWatts?: number }).modelWatts) : null,
    ]).filter((v): v is number => v !== null && v !== undefined);
    
    if (values.length === 0) return [0, 500];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || 50;
    return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
  }, [mergedChartData, showWkg, showComparison, showModel]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 rounded-lg">
        {error}
      </div>
    );
  }

  const valueKey = showWkg ? "wkg" : "watts";
  const compValueKey = showWkg ? "compWkg" : "compWatts";
  const modelKey = showWkg ? "modelWkg" : "modelWatts";
  const unit = showWkg ? "W/kg" : "W";

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Power Curve
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Your best power output at each duration
        </p>
      </div>

      {/* Controls */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          {/* Date presets */}
          <div className="flex gap-2">
            {DATE_PRESETS.map((preset, i) => (
              <button
                key={preset.label}
                onClick={() => setActivePreset(i)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  activePreset === i
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-4 ml-auto">
            {/* W/kg toggle */}
            {userWeight && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showWkg}
                  onChange={(e) => setShowWkg(e.target.checked)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">W/kg</span>
              </label>
            )}

            {/* Model toggle */}
            {fitness?.current && (
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showModel}
                  onChange={(e) => setShowModel(e.target.checked)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">Show model</span>
              </label>
            )}

            {/* Comparison toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={showComparison}
                onChange={(e) => setShowComparison(e.target.checked)}
                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-sm text-gray-700 dark:text-gray-300">Compare</span>
            </label>

            {showComparison && (
              <select
                value={comparisonPreset}
                onChange={(e) => setComparisonPreset(Number(e.target.value))}
                className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                {DATE_PRESETS.map((preset, i) => (
                  <option key={preset.label} value={i}>{preset.label}</option>
                ))}
              </select>
            )}
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="flex items-center gap-6 mb-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-indigo-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">
              {DATE_PRESETS[activePreset].label}
            </span>
          </div>
          {showComparison && (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {DATE_PRESETS[comparisonPreset].label}
              </span>
            </div>
          )}
          {showModel && fitness?.current && (
            <div className="flex items-center gap-2">
              <div className="w-6 h-0.5 bg-purple-500" style={{ borderStyle: "dashed", borderWidth: 1 }}></div>
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Model (CP: {fitness.current.cp_watts}W)
              </span>
            </div>
          )}
        </div>

        {curveData.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
            No power data available
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={mergedChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              
              <XAxis
                dataKey="logDuration"
                type="number"
                domain={[Math.log10(1), Math.log10(7200)]}
                tickFormatter={(v) => formatDuration(Math.pow(10, v))}
                ticks={KEY_DURATIONS.map(d => Math.log10(d))}
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={{ stroke: "#d1d5db" }}
                tickLine={{ stroke: "#d1d5db" }}
              />
              
              <YAxis
                domain={yDomain}
                tick={{ fontSize: 12, fill: "#6b7280" }}
                axisLine={{ stroke: "#d1d5db" }}
                tickLine={{ stroke: "#d1d5db" }}
                label={{ value: unit, angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
              />

              {/* Key duration reference lines */}
              {KEY_DURATIONS.map((d) => (
                <ReferenceLine
                  key={d}
                  x={Math.log10(d)}
                  stroke="#e5e7eb"
                  strokeDasharray="2 2"
                />
              ))}

              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const point = payload[0].payload;
                  return (
                    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
                      <div className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                        {formatDuration(point.duration)}
                      </div>
                      <div className="space-y-1 text-sm">
                        {point[valueKey] !== null && (
                          <div className="flex justify-between gap-4">
                            <span className="text-indigo-600">Power</span>
                            <span className="font-medium">
                              {showWkg ? point[valueKey]?.toFixed(2) : point[valueKey]} {unit}
                            </span>
                          </div>
                        )}
                        {showComparison && point[compValueKey] !== null && (
                          <div className="flex justify-between gap-4">
                            <span className="text-emerald-600">Comparison</span>
                            <span className="font-medium">
                              {showWkg ? point[compValueKey]?.toFixed(2) : point[compValueKey]} {unit}
                            </span>
                          </div>
                        )}
                        {point.achievedDate && (
                          <div className="text-gray-500 text-xs pt-1 border-t border-gray-200 dark:border-gray-600">
                            {new Date(point.achievedDate).toLocaleDateString()} ({point.daysAgo}d ago)
                          </div>
                        )}
                      </div>
                    </div>
                  );
                }}
              />

              {/* Model curve (dashed) */}
              {showModel && (
                <Line
                  type="monotone"
                  dataKey={modelKey}
                  stroke="#a855f7"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  connectNulls
                />
              )}

              {/* Comparison curve */}
              {showComparison && (
                <Line
                  type="monotone"
                  dataKey={compValueKey}
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                />
              )}

              {/* Main curve */}
              <Line
                type="monotone"
                dataKey={valueKey}
                stroke="#6366f1"
                strokeWidth={2}
                dot={{ fill: "#6366f1", r: 4 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Data table */}
      {curveData.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Duration</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Power</th>
                {userWeight && (
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">W/kg</th>
                )}
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Date</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Freshness</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              {curveData.map((point) => {
                const isKey = KEY_DURATIONS.includes(point.duration_seconds);
                return (
                  <tr 
                    key={point.duration_seconds}
                    className={isKey ? "bg-indigo-50 dark:bg-indigo-900/10" : ""}
                  >
                    <td className={`px-4 py-3 ${isKey ? "font-semibold" : ""} text-gray-900 dark:text-white`}>
                      {formatDuration(point.duration_seconds)}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-gray-900 dark:text-white">
                      {point.watts} W
                    </td>
                    {userWeight && (
                      <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">
                        {(point.watts / userWeight).toFixed(2)} W/kg
                      </td>
                    )}
                    <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-400">
                      {new Date(point.achieved_date).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                        style={{ 
                          backgroundColor: getStalenessColor(point.days_ago) + "20",
                          color: getStalenessColor(point.days_ago),
                        }}
                      >
                        {getStalenessLabel(point.days_ago)} ({point.days_ago}d)
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
