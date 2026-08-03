import { useEffect, useCallback } from "react";
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

// Tooltip styles (extracted for consistency)
const TOOLTIP_STYLE = {
  container: {
    backgroundColor: "white",
    border: "1px solid #e5e7eb",
    borderRadius: "8px",
    fontSize: "14px",
    padding: "8px 12px",
  },
  label: { color: "#6b7280", marginBottom: 4 },
} as const;

interface ChartConfig {
  key: string;
  label: string;
  unit: string;
  color: string;
  dataKey: string;
}

interface ChartExpandModalProps {
  chart: ChartConfig;
  data: Array<Record<string, number | null>>;
  axisMode: "time" | "distance";
  onToggleAxis: () => void;
  onClose: () => void;
  formatDistance: (m: number) => string;
  formatTime: (s: number) => string;
  // Threshold values for reference lines
  ftpWatts?: number | null;
  lthrBpm?: number | null;
}

export function ChartExpandModal({
  chart,
  data,
  axisMode,
  onToggleAxis,
  onClose,
  formatDistance,
  formatTime,
  ftpWatts,
  lthrBpm,
}: ChartExpandModalProps) {
  // Handle escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    // Prevent body scroll when modal is open
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [handleKeyDown]);

  // Handle click outside
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // X-axis setup based on mode
  const xKey = axisMode === "distance" ? "distance_m" : "elapsed";
  const tickFormatter =
    axisMode === "distance"
      ? (v: number) => formatDistance(v)
      : (v: number) => formatTime(v);

  // Calculate Y-axis domain with margin
  const values = data
    .map((d) => d[chart.dataKey])
    .filter((v): v is number => v !== null && v !== undefined);
  
  if (values.length === 0) {
    return null;
  }

  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const range = maxVal - minVal;
  const margin = range * 0.1 || 5;
  const yMin = Math.max(0, Math.floor(minVal - margin));
  const yMax = Math.ceil(maxVal + margin);

  // Calculate x-axis ticks
  const xValues = data
    .map((d) => d[xKey])
    .filter((v): v is number => v !== null && v !== undefined);
  const xMin = Math.min(...xValues);
  const xMax = Math.max(...xValues);
  const xRange = xMax - xMin;
  const tickCount = 10;
  const tickInterval = xRange / tickCount;
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) =>
    Math.round(xMin + i * tickInterval)
  );

  // Determine if we should show threshold line
  const showFtpLine = chart.key === "power" && ftpWatts && ftpWatts > 0;
  const showLthrLine = chart.key === "hr" && lthrBpm && lthrBpm > 0;

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl flex flex-col"
        style={{
          width: "90vw",
          height: "70vh",
          maxHeight: "700px",
          maxWidth: "1400px",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex-shrink-0">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {chart.label}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Expanded view
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Axis toggle */}
            <button
              onClick={onToggleAxis}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                axisMode === "distance"
                  ? "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300"
                  : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
              }`}
            >
              {axisMode === "distance" ? "Distance" : "Time"}
            </button>
            {/* Close button */}
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              aria-label="Close"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Chart container */}
        <div className="flex-1 p-6 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey={xKey}
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={tickFormatter}
                ticks={ticks}
                interval={0}
                tick={{ fontSize: 12, fill: "#6b7280" }}
                axisLine={{ stroke: "#d1d5db" }}
                tickLine={{ stroke: "#d1d5db" }}
              />
              <YAxis
                domain={[yMin, yMax]}
                tick={{ fontSize: 12, fill: "#6b7280" }}
                axisLine={{ stroke: "#d1d5db" }}
                tickLine={{ stroke: "#d1d5db" }}
                label={{
                  value: chart.unit,
                  angle: -90,
                  position: "insideLeft",
                  fontSize: 12,
                  fill: "#6b7280",
                }}
              />
              <Tooltip
                content={({ active, payload, label }) => {
                  if (!active || !payload?.length) return null;
                  const value = payload[0].value;
                  const labelStr = typeof label === "number"
                    ? (axisMode === "distance" ? formatDistance(label) : formatTime(label))
                    : String(label);
                  return (
                    <div style={TOOLTIP_STYLE.container}>
                      <div style={TOOLTIP_STYLE.label}>{labelStr}</div>
                      <div>
                        {chart.label}: {typeof value === "number" ? value.toFixed(1) : value} {chart.unit}
                      </div>
                    </div>
                  );
                }}
              />
              
              {/* FTP reference line for Power chart */}
              {showFtpLine && (
                <ReferenceLine
                  y={ftpWatts}
                  stroke="#f59e0b"
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  label={{
                    value: `FTP ${ftpWatts}W`,
                    position: "right",
                    fill: "#f59e0b",
                    fontSize: 12,
                  }}
                />
              )}
              
              {/* LTHR reference line for HR chart */}
              {showLthrLine && (
                <ReferenceLine
                  y={lthrBpm}
                  stroke="#ef4444"
                  strokeDasharray="5 5"
                  strokeWidth={2}
                  label={{
                    value: `LTHR ${lthrBpm}`,
                    position: "right",
                    fill: "#ef4444",
                    fontSize: 12,
                  }}
                />
              )}

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
        </div>

        {/* Footer with threshold legend if applicable */}
        {(showFtpLine || showLthrLine) && (
          <div className="px-6 py-3 border-t border-gray-200 dark:border-gray-700 flex-shrink-0">
            <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
              {showFtpLine && (
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0.5 bg-amber-500" style={{ backgroundImage: 'linear-gradient(90deg, #f59e0b 50%, transparent 50%)', backgroundSize: '8px 100%' }} />
                  <span>FTP: {ftpWatts}W</span>
                </div>
              )}
              {showLthrLine && (
                <div className="flex items-center gap-2">
                  <div className="w-6 h-0.5 bg-red-500" style={{ backgroundImage: 'linear-gradient(90deg, #ef4444 50%, transparent 50%)', backgroundSize: '8px 100%' }} />
                  <span>LTHR: {lthrBpm} bpm</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
