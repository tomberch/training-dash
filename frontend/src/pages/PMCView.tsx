import { useState, useEffect, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import type { PMCPoint, ThresholdEntry } from "../api";
import { fetchPMC, fetchThresholds } from "../api";
import { TSB_ZONES, getTSBZone } from "../constants";

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

interface DatePreset {
  label: string;
  weeks?: number;
  ytd?: boolean;
  all?: boolean;
}

const DATE_PRESETS: DatePreset[] = [
  { label: "4 weeks", weeks: 4 },
  { label: "8 weeks", weeks: 8 },
  { label: "12 weeks", weeks: 12 },
  { label: "YTD", ytd: true },
  { label: "All", all: true },
];

export function PMCView() {
  const [pmcData, setPmcData] = useState<PMCPoint[]>([]);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activePreset, setActivePreset] = useState<number>(2); // Default: 12 weeks
  const [customStart, setCustomStart] = useState<string>("");
  const [customEnd, setCustomEnd] = useState<string>("");
  const [useCustomRange, setUseCustomRange] = useState(false);

  // Compute date range based on preset or custom
  const { start, end } = useMemo(() => {
    const today = new Date();
    const endDate = today.toISOString().split("T")[0];
    
    if (useCustomRange && customStart && customEnd) {
      return { start: customStart, end: customEnd };
    }
    
    const preset = DATE_PRESETS[activePreset];
    if (preset.weeks) {
      const startDate = new Date(today);
      startDate.setDate(startDate.getDate() - preset.weeks * 7);
      return { start: startDate.toISOString().split("T")[0], end: endDate };
    }
    if (preset.ytd) {
      return { start: `${today.getFullYear()}-01-01`, end: endDate };
    }
    // All time - no start date
    return { start: undefined, end: endDate };
  }, [activePreset, useCustomRange, customStart, customEnd]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    
    Promise.all([
      fetchPMC(start, end),
      fetchThresholds(),
    ])
      .then(([pmc, thresh]) => {
        setPmcData(pmc);
        setThresholds(thresh);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message || "Failed to load PMC data");
        setLoading(false);
      });
  }, [start, end]);

  // Get current TSB (last data point)
  const currentTSB = pmcData.length > 0 ? pmcData[pmcData.length - 1].tsb : 0;
  const currentZone = getTSBZone(currentTSB);

  // FTP changes within the date range
  const ftpMarkers = useMemo(() => {
    if (!start) return [];
    return thresholds
      .filter(t => t.ftp_watts && t.effective_date >= start && t.effective_date <= (end || ""))
      .map(t => ({ date: t.effective_date, ftp: t.ftp_watts! }));
  }, [thresholds, start, end]);

  // Y-axis domain with padding
  const yDomain = useMemo(() => {
    if (pmcData.length === 0) return [-50, 100];
    const allValues = pmcData.flatMap(p => [p.ctl, p.atl, p.tsb]);
    const min = Math.min(...allValues);
    const max = Math.max(...allValues);
    const padding = (max - min) * 0.1 || 10;
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [pmcData]);

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

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header with form badge */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Performance Management Chart
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Track your fitness, fatigue, and form over time
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
            Current Form
          </div>
          <span
            className="inline-flex items-center px-3 py-1 rounded-full text-sm font-semibold"
            style={{ backgroundColor: currentZone.color, color: "#1f2937" }}
          >
            {currentZone.name} ({currentTSB.toFixed(0)})
          </span>
        </div>
      </div>

      {/* Date range controls */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          {/* Presets */}
          <div className="flex gap-2">
            {DATE_PRESETS.map((preset, i) => (
              <button
                key={preset.label}
                onClick={() => {
                  setActivePreset(i);
                  setUseCustomRange(false);
                }}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  !useCustomRange && activePreset === i
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Custom range */}
          <div className="flex items-center gap-2 ml-auto">
            <input
              type="date"
              value={customStart}
              onChange={(e) => {
                setCustomStart(e.target.value);
                setUseCustomRange(true);
              }}
              className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <span className="text-gray-500">to</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => {
                setCustomEnd(e.target.value);
                setUseCustomRange(true);
              }}
              className="px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
          </div>
        </div>
      </div>

      {/* PMC Chart */}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center gap-6 mb-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">CTL (Fitness)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-pink-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">ATL (Fatigue)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span className="text-sm text-gray-600 dark:text-gray-400">TSB (Form)</span>
          </div>
        </div>

        {pmcData.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">
            No data available for the selected date range
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={pmcData}>
              {/* TSB zone backgrounds */}
              {TSB_ZONES.map((zone) => (
                <ReferenceArea
                  key={zone.name}
                  y1={Math.max(zone.min, yDomain[0])}
                  y2={Math.min(zone.max, yDomain[1])}
                  fill={zone.color}
                  fillOpacity={0.3}
                />
              ))}

              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                tick={{ fontSize: 11, fill: "#6b7280" }}
                axisLine={{ stroke: "#d1d5db" }}
                tickLine={{ stroke: "#d1d5db" }}
              />
              
              <YAxis
                domain={yDomain}
                tick={{ fontSize: 12, fill: "#6b7280" }}
                axisLine={{ stroke: "#d1d5db" }}
                tickLine={{ stroke: "#d1d5db" }}
              />

              {/* Zero line for TSB reference */}
              <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />

              {/* FTP change markers */}
              {ftpMarkers.map((marker) => (
                <ReferenceLine
                  key={marker.date}
                  x={marker.date}
                  stroke="#8b5cf6"
                  strokeDasharray="5 5"
                  label={{
                    value: `FTP: ${marker.ftp}W`,
                    position: "top",
                    fill: "#8b5cf6",
                    fontSize: 10,
                  }}
                />
              ))}

              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const point = payload[0].payload as PMCPoint;
                  const zone = getTSBZone(point.tsb);
                  return (
                    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg p-3">
                      <div className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                        {new Date(point.date).toLocaleDateString(undefined, {
                          weekday: "short",
                          month: "short",
                          day: "numeric",
                          year: "numeric",
                        })}
                      </div>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between gap-4">
                          <span className="text-blue-600">CTL (Fitness)</span>
                          <span className="font-medium">{point.ctl.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-pink-600">ATL (Fatigue)</span>
                          <span className="font-medium">{point.atl.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-amber-600">TSB (Form)</span>
                          <span className="font-medium">{point.tsb.toFixed(1)}</span>
                        </div>
                        <div className="pt-1 border-t border-gray-200 dark:border-gray-600 mt-1">
                          <span
                            className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                            style={{ backgroundColor: zone.color, color: "#1f2937" }}
                          >
                            {zone.name}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                }}
              />

              <Line
                type="monotone"
                dataKey="ctl"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                name="CTL"
              />
              <Line
                type="monotone"
                dataKey="atl"
                stroke="#ec4899"
                strokeWidth={2}
                dot={false}
                name="ATL"
              />
              <Line
                type="monotone"
                dataKey="tsb"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
                name="TSB"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Zone legend */}
      <div className="mt-4 flex flex-wrap gap-3 justify-center">
        {TSB_ZONES.map((zone) => (
          <div key={zone.name} className="flex items-center gap-2">
            <div
              className="w-4 h-4 rounded"
              style={{ backgroundColor: zone.color }}
            ></div>
            <span className="text-xs text-gray-600 dark:text-gray-400">
              {zone.name} ({zone.min > -100 ? zone.min : "<-25"} to {zone.max < 100 ? zone.max : ">25"})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
