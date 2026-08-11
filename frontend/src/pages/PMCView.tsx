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
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

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

  // Check if FTP is configured (needed for TSS calculation)
  const hasFTP = thresholds.length > 0 && thresholds[0].ftp_watts !== null;

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
      <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Header skeleton */}
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-8 w-72 mb-2" />
            <Skeleton className="h-4 w-56" />
          </div>
          <div className="text-right">
            <Skeleton className="h-3 w-20 mb-1" />
            <Skeleton className="h-8 w-32 rounded-full" />
          </div>
        </div>
        
        {/* Date range selector skeleton */}
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-8 w-20 rounded" />
          ))}
        </div>
        
        {/* Chart skeleton */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="h-80 bg-muted rounded flex items-end justify-around p-4 gap-1">
            {[40, 55, 35, 60, 45, 70, 50, 65, 45, 75, 55, 80, 60, 50, 70, 45, 60, 75, 50, 65].map((h, i) => (
              <Skeleton key={i} className="flex-1 rounded-t" style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
        
        {/* Stats row skeleton */}
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-card rounded-lg border border-border p-4">
              <Skeleton className="h-3 w-12 mb-2" />
              <Skeleton className="h-7 w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header with form badge */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Performance Management Chart
          </h1>
          <p className="text-body-secondary mt-1">
            Track your fitness, fatigue, and form over time
          </p>
        </div>
        <div className="text-right">
          <div className="text-caption uppercase tracking-wide mb-1">
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

      {/* FTP missing banner */}
      {!hasFTP && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-4 mb-6">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-warning flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="text-sm font-medium text-warning">FTP not set — TSS cannot be calculated</p>
              <p className="text-body-secondary mt-1">
                Upload more rides to auto-detect FTP, or{" "}
                <a href="/settings" className="text-primary hover:underline">set manually in Settings → Thresholds</a>.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Date range controls */}
      <div className="bg-card rounded-lg border border-border p-4 mb-6">
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
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-fast ${
                  !useCustomRange && activePreset === i
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground hover:bg-muted/80"
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
              className="px-2 py-1.5 text-sm border border-input-border rounded-lg bg-input text-foreground"
            />
            <span className="text-muted-foreground">to</span>
            <input
              type="date"
              value={customEnd}
              onChange={(e) => {
                setCustomEnd(e.target.value);
                setUseCustomRange(true);
              }}
              className="px-2 py-1.5 text-sm border border-input-border rounded-lg bg-input text-foreground"
            />
          </div>
        </div>
      </div>

      {/* PMC Chart */}
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="flex items-center gap-6 mb-4">
          <div className="flex items-center gap-2 group relative">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-body-secondary">CTL (Fitness)</span>
            <div className="absolute bottom-full left-0 mb-2 px-3 py-2 bg-popover text-popover-foreground text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none w-64 z-10 border border-border">
              <strong>Chronic Training Load</strong> — your long-term fitness level, calculated from the rolling average of daily TSS over ~42 days.
            </div>
          </div>
          <div className="flex items-center gap-2 group relative">
            <div className="w-3 h-3 rounded-full bg-pink-500"></div>
            <span className="text-body-secondary">ATL (Fatigue)</span>
            <div className="absolute bottom-full left-0 mb-2 px-3 py-2 bg-popover text-popover-foreground text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none w-64 z-10 border border-border">
              <strong>Acute Training Load</strong> — your short-term fatigue, calculated from the rolling average of daily TSS over ~7 days.
            </div>
          </div>
          <div className="flex items-center gap-2 group relative">
            <div className="w-3 h-3 rounded-full bg-amber-500"></div>
            <span className="text-body-secondary">TSB (Form)</span>
            <div className="absolute bottom-full left-0 mb-2 px-3 py-2 bg-popover text-popover-foreground text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none w-64 z-10 border border-border">
              <strong>Training Stress Balance</strong> — CTL minus ATL. Positive = fresh and ready to perform. Negative = fatigued and building fitness.
            </div>
          </div>
        </div>

        {pmcData.length === 0 ? (
          <div className="bg-card rounded-lg border border-border">
            <EmptyState
              icon={
                <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              }
              title="No data for this date range"
              description="Try selecting a different date range, or upload activities with TSS data to see your performance trends."
            />
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

              {/* Today marker */}
              <ReferenceLine
                x={new Date().toISOString().split("T")[0]}
                stroke="#10b981"
                strokeWidth={2}
                label={{
                  value: "Today",
                  position: "top",
                  fill: "#10b981",
                  fontSize: 10,
                  fontWeight: 600,
                }}
              />

              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const point = payload[0].payload as PMCPoint;
                  const zone = getTSBZone(point.tsb);
                  return (
                    <div className="bg-card border border-border rounded-lg shadow-lg p-3">
                      <div className="text-sm font-medium text-foreground mb-2">
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
                        <div className="pt-1 border-t border-border mt-1">
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
            <span className="text-caption">
              {zone.name} ({zone.min > -100 ? zone.min : "<-25"} to {zone.max < 100 ? zone.max : ">25"})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
