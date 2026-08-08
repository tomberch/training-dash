import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/utils";

// Types
export type MetricSource = "manual" | "calculated" | "device";

export interface MetricEntry {
  id: string;
  effective_date: string;
  value: number;
  source: MetricSource;
  notes?: string;
}

export type TimeRange = "6M" | "1Y" | "2Y" | "all";

export interface MetricTimelineChartProps {
  entries: MetricEntry[];
  chartType: "step" | "line";
  unit: string;
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  onPointClick?: (entry: MetricEntry) => void;
}

// Time range options
const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: "6M", label: "6M" },
  { value: "1Y", label: "1Y" },
  { value: "2Y", label: "2Y" },
  { value: "all", label: "All" },
];

// Source styling
const SOURCE_COLORS: Record<MetricSource, { fill: string; stroke: string }> = {
  manual: { fill: "hsl(var(--primary))", stroke: "hsl(var(--primary))" },
  calculated: { fill: "transparent", stroke: "hsl(var(--success))" },
  device: { fill: "hsl(var(--warning))", stroke: "hsl(var(--warning))" },
};

// Filter entries by time range
function filterByTimeRange(entries: MetricEntry[], range: TimeRange): MetricEntry[] {
  if (range === "all") return entries;

  const now = new Date();
  const cutoff = new Date();

  switch (range) {
    case "6M":
      cutoff.setMonth(now.getMonth() - 6);
      break;
    case "1Y":
      cutoff.setFullYear(now.getFullYear() - 1);
      break;
    case "2Y":
      cutoff.setFullYear(now.getFullYear() - 2);
      break;
  }

  return entries.filter((e) => new Date(e.effective_date) >= cutoff);
}

// Format date for display
function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function formatAxisDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
}

// Custom dot component
interface CustomDotProps {
  cx?: number;
  cy?: number;
  payload?: MetricEntry;
  onClick?: (entry: MetricEntry) => void;
}

function CustomDot({ cx, cy, payload, onClick }: CustomDotProps) {
  if (cx === undefined || cy === undefined || !payload) return null;

  const colors = SOURCE_COLORS[payload.source];
  const isDevice = payload.source === "device";
  const size = 6;

  const handleClick = () => {
    if (onClick && payload) {
      onClick(payload);
    }
  };

  if (isDevice) {
    // Square for device
    return (
      <rect
        x={cx - size / 2}
        y={cy - size / 2}
        width={size}
        height={size}
        fill={colors.fill}
        stroke={colors.stroke}
        strokeWidth={1.5}
        className="cursor-pointer"
        onClick={handleClick}
      />
    );
  }

  // Circle for manual/calculated
  return (
    <circle
      cx={cx}
      cy={cy}
      r={size / 2}
      fill={colors.fill}
      stroke={colors.stroke}
      strokeWidth={2}
      className="cursor-pointer"
      onClick={handleClick}
    />
  );
}

// Custom tooltip
interface TooltipProps {
  active?: boolean;
  payload?: Array<{ payload: MetricEntry }>;
  unit: string;
}

function CustomTooltip({ active, payload, unit }: TooltipProps) {
  if (!active || !payload?.[0]) return null;

  const entry = payload[0].payload;
  const sourceLabel = entry.source.charAt(0).toUpperCase() + entry.source.slice(1);
  const sourceColor = SOURCE_COLORS[entry.source];

  return (
    <div className="bg-card border border-border rounded-lg p-3 shadow-lg min-w-[140px]">
      <p className="font-medium text-foreground text-sm">
        {formatDate(entry.effective_date)}
      </p>
      <p className="text-lg font-bold text-foreground mt-1">
        {entry.value} {unit}
      </p>
      <div className="flex items-center gap-1.5 mt-2">
        <span
          className="w-2.5 h-2.5 rounded-full"
          style={{ backgroundColor: sourceColor.stroke }}
        />
        <span className="text-xs text-muted-foreground">{sourceLabel}</span>
      </div>
      {entry.notes && (
        <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
          {entry.notes}
        </p>
      )}
    </div>
  );
}

// Time range selector
interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <div className="inline-flex rounded-md bg-muted p-1 gap-0.5" role="group" aria-label="Time range">
      {TIME_RANGES.map((range) => (
        <button
          key={range.value}
          type="button"
          aria-pressed={value === range.value}
          onClick={() => onChange(range.value)}
          className={cn(
            "px-3 py-1 text-sm font-medium rounded transition-colors",
            value === range.value
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {range.label}
        </button>
      ))}
    </div>
  );
}

// Main component
export function MetricTimelineChart({
  entries,
  chartType,
  unit,
  timeRange,
  onTimeRangeChange,
  onPointClick,
}: MetricTimelineChartProps) {
  // Filter and sort entries
  const filteredEntries = useMemo(() => {
    const filtered = filterByTimeRange(entries, timeRange);
    return [...filtered].sort(
      (a, b) => new Date(a.effective_date).getTime() - new Date(b.effective_date).getTime()
    );
  }, [entries, timeRange]);

  // Compute Y-axis domain with padding
  const yDomain = useMemo(() => {
    if (filteredEntries.length === 0) return [0, 100];
    const values = filteredEntries.map((e) => e.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.1 || max * 0.1;
    return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
  }, [filteredEntries]);

  const lineType = chartType === "step" ? "stepAfter" : "monotone";

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <TimeRangeSelector value={timeRange} onChange={onTimeRangeChange} />
      </div>

      {filteredEntries.length === 0 ? (
        <div className="h-[200px] flex items-center justify-center text-muted-foreground text-sm">
          No data for selected time range
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart
            data={filteredEntries}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <XAxis
              dataKey="effective_date"
              tickFormatter={formatAxisDate}
              tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
              axisLine={{ stroke: "hsl(var(--border))" }}
              tickLine={{ stroke: "hsl(var(--border))" }}
              minTickGap={40}
            />
            <YAxis
              domain={yDomain}
              tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
              axisLine={{ stroke: "hsl(var(--border))" }}
              tickLine={{ stroke: "hsl(var(--border))" }}
              width={45}
              tickFormatter={(v) => `${v}${unit.length <= 2 ? unit : ""}`}
            />
            <Tooltip content={<CustomTooltip unit={unit} />} />
            <Line
              type={lineType}
              dataKey="value"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={(props) => (
                <CustomDot {...props} onClick={onPointClick} />
              )}
              activeDot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 text-xs text-muted-foreground">
        <div className="flex items-center gap-1.5">
          <span
            className="w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: SOURCE_COLORS.manual.fill }}
          />
          <span>Manual</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="w-2.5 h-2.5 rounded-full border-2"
            style={{ borderColor: SOURCE_COLORS.calculated.stroke }}
          />
          <span>Calculated</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="w-2.5 h-2.5"
            style={{ backgroundColor: SOURCE_COLORS.device.fill }}
          />
          <span>Device</span>
        </div>
      </div>
    </div>
  );
}
