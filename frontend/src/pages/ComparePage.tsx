import { useState, useEffect, useRef, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { Activity, GeoJSONFeatureCollection, SameRouteResponse, CompareResponse, GapPoint } from "../api";
import { fetchActivity, fetchActivityRecords, fetchSameRouteActivities, fetchComparison } from "../api";
import { ActivitySelector } from "../components/ActivitySelector";
import { ResizableMap } from "../components/ResizableMap";
import { useResizableMap } from "../hooks/useResizableMap";
import { ChartErrorBoundary } from "../components/ErrorBoundary";
import { Skeleton } from "@/components/ui/skeleton";
import { ChartSkeleton } from "@/components/ui/skeletons";
import { formatDistance, formatSpeed, formatTime, formatElevation, formatActivityDate, formatRelativeTime } from "../format";

// Gap coloring thresholds
function gapColor(gap: number): string {
  if (gap < -0.5) return "#10b981"; // green = faster (negative gap means ahead)
  if (gap > 0.5) return "#ef4444"; // red = slower (positive gap means behind)
  return "#6366f1"; // neutral indigo
}

function formatDistanceKm(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

function formatGap(seconds: number): string {
  const abs = Math.abs(seconds);
  const sign = seconds >= 0 ? "+" : "-";
  if (abs < 60) return `${sign}${abs.toFixed(0)}s`;
  const mins = Math.floor(abs / 60);
  const secs = Math.floor(abs % 60);
  return `${sign}${mins}:${secs.toString().padStart(2, "0")}`;
}

interface GapChartPoint {
  distance_m: number;
  gap_s: number;
  elevation_m: number | null;
}

interface PowerChartPoint {
  distance_m: number;
  base_power: number | null;
  compare_power: number | null;
}

// Apply smoothing to power data (10s equivalent based on typical cycling speed)
function smoothPowerData(
  baseFeatures: GeoJSONFeatureCollection["features"],
  compareFeatures: GeoJSONFeatureCollection["features"],
  windowMeters: number = 100
): PowerChartPoint[] {
  // Build maps by distance
  const baseByDist = new Map<number, number | null>();
  const compareByDist = new Map<number, number | null>();
  
  for (const f of baseFeatures) {
    baseByDist.set(f.properties.distance_m, f.properties.power_w);
  }
  for (const f of compareFeatures) {
    compareByDist.set(f.properties.distance_m, f.properties.power_w);
  }
  
  // Get all unique distances, sorted
  const allDistances = Array.from(
    new Set([...baseByDist.keys(), ...compareByDist.keys()])
  ).sort((a, b) => a - b);
  
  // Sample at 50m intervals for cleaner chart
  const sampledDistances: number[] = [];
  const maxDist = Math.max(...allDistances);
  for (let d = 0; d <= maxDist; d += 50) {
    sampledDistances.push(d);
  }
  
  const result: PowerChartPoint[] = [];
  
  for (const dist of sampledDistances) {
    const windowStart = dist - windowMeters / 2;
    const windowEnd = dist + windowMeters / 2;
    
    // Collect points in window for base
    let baseSum = 0;
    let baseCount = 0;
    for (const [d, p] of baseByDist) {
      if (d >= windowStart && d <= windowEnd && p !== null) {
        baseSum += p;
        baseCount++;
      }
    }
    
    // Collect points in window for compare
    let compareSum = 0;
    let compareCount = 0;
    for (const [d, p] of compareByDist) {
      if (d >= windowStart && d <= windowEnd && p !== null) {
        compareSum += p;
        compareCount++;
      }
    }
    
    result.push({
      distance_m: dist,
      base_power: baseCount > 0 ? baseSum / baseCount : null,
      compare_power: compareCount > 0 ? compareSum / compareCount : null,
    });
  }
  
  return result;
}

interface PowerComparisonChartProps {
  baseGeojson: GeoJSONFeatureCollection | null;
  compareGeojson: GeoJSONFeatureCollection | null;
  baseActivity: Activity;
  compareActivity: Activity;
  onHover: (state: unknown) => void;
  onLeave: () => void;
}

function PowerComparisonChart({
  baseGeojson,
  compareGeojson,
  baseActivity,
  compareActivity,
  onHover,
  onLeave,
}: PowerComparisonChartProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const chartData = useMemo(() => {
    if (!baseGeojson || !compareGeojson) return [];
    return smoothPowerData(baseGeojson.features, compareGeojson.features);
  }, [baseGeojson, compareGeojson]);
  
  // Check if either activity has power data
  const hasPowerData = useMemo(() => {
    if (!chartData.length) return false;
    return chartData.some(p => p.base_power !== null || p.compare_power !== null);
  }, [chartData]);
  
  if (!hasPowerData) {
    return (
      <div className="bg-card rounded-lg border border-border p-4">
        <h3 className="text-sm font-medium text-muted-foreground">
          Power Comparison
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">
          No power data available for these activities.
        </p>
      </div>
    );
  }
  
  return (
    <div className="bg-card rounded-lg border border-border">
      {/* Collapsible header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-muted/50 transition-fast rounded-t-lg"
      >
        <h3 className="text-sm font-medium text-foreground">
          Power Comparison
        </h3>
        <div className="flex items-center gap-4">
          {/* Legend preview when collapsed */}
          {!isExpanded && (
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-indigo-500" />
                <span>{baseActivity.title || "Base"}</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="w-3 h-0.5 bg-amber-500" />
                <span>{compareActivity.title || "Compare"}</span>
              </div>
            </div>
          )}
          <svg
            className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>
      
      {/* Chart content */}
      {isExpanded && (
        <div className="px-4 pb-4">
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartData}
                onMouseMove={onHover}
                onMouseLeave={onLeave}
                margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                <XAxis
                  dataKey="distance_m"
                  tickFormatter={formatDistanceKm}
                  stroke="#9ca3af"
                  fontSize={12}
                />
                <YAxis
                  stroke="#9ca3af"
                  fontSize={12}
                  tickFormatter={(v) => `${Math.round(v)}W`}
                  domain={[0, "auto"]}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1f2937",
                    border: "1px solid #374151",
                    borderRadius: "0.375rem",
                    color: "#f9fafb",
                  }}
                  formatter={(value, name) => {
                    const v = value as number | null;
                    if (v === null) return ["No data", name];
                    if (name === "base_power") {
                      return [`${Math.round(v)} W`, baseActivity.title || "Base"];
                    }
                    if (name === "compare_power") {
                      return [`${Math.round(v)} W`, compareActivity.title || "Compare"];
                    }
                    return [v, name];
                  }}
                  labelFormatter={(label) => formatDistanceKm(label as number)}
                />
                
                {/* Base activity power line */}
                <Line
                  type="monotone"
                  dataKey="base_power"
                  stroke="#6366f1"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  name="base_power"
                />
                
                {/* Compare activity power line */}
                <Line
                  type="monotone"
                  dataKey="compare_power"
                  stroke="#f59e0b"
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  name="compare_power"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          
          {/* Legend */}
          <div className="flex items-center justify-center gap-6 mt-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-indigo-500" />
              <span>{baseActivity.title || "Base"}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-4 h-0.5 bg-amber-500" />
              <span>{compareActivity.title || "Compare"}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Stats comparison table types
interface StatRow {
  label: string;
  baseValue: string | null;
  compareValue: string | null;
  baseRaw: number | null;
  compareRaw: number | null;
  delta: string | null;
  winner: "base" | "compare" | "tie" | null;
  lowerIsBetter?: boolean;
}

interface StatsTableProps {
  baseActivity: Activity;
  compareActivity: Activity;
  comparison: CompareResponse | null;
}

function StatsTable({ baseActivity, compareActivity, comparison }: StatsTableProps) {
  const stats = useMemo((): StatRow[] => {
    const rows: StatRow[] = [];
    
    // Helper to determine winner (higher is better by default, unless lowerIsBetter)
    const getWinner = (
      base: number | null,
      compare: number | null,
      lowerIsBetter = false
    ): "base" | "compare" | "tie" | null => {
      if (base === null || compare === null) return null;
      if (Math.abs(base - compare) < 0.01) return "tie";
      if (lowerIsBetter) {
        return base < compare ? "base" : "compare";
      }
      return base > compare ? "base" : "compare";
    };
    
    // Helper to format delta
    const formatDelta = (
      base: number | null,
      compare: number | null,
      formatter: (v: number) => string
    ): string | null => {
      if (base === null || compare === null) return null;
      const diff = compare - base;
      if (Math.abs(diff) < 0.01) return "—";
      const sign = diff > 0 ? "+" : "";
      return sign + formatter(diff);
    };

    // Moving Time (lower is better)
    rows.push({
      label: "Moving Time",
      baseValue: formatTime(baseActivity.moving_time_s),
      compareValue: formatTime(compareActivity.moving_time_s),
      baseRaw: baseActivity.moving_time_s,
      compareRaw: compareActivity.moving_time_s,
      delta: formatDelta(
        baseActivity.moving_time_s,
        compareActivity.moving_time_s,
        (v) => formatTime(Math.abs(v))
      ),
      winner: getWinner(baseActivity.moving_time_s, compareActivity.moving_time_s, true),
      lowerIsBetter: true,
    });

    // Distance
    rows.push({
      label: "Distance",
      baseValue: formatDistance(baseActivity.total_distance_m),
      compareValue: formatDistance(compareActivity.total_distance_m),
      baseRaw: baseActivity.total_distance_m,
      compareRaw: compareActivity.total_distance_m,
      delta: formatDelta(
        baseActivity.total_distance_m,
        compareActivity.total_distance_m,
        (v) => formatDistance(Math.abs(v))
      ),
      winner: getWinner(baseActivity.total_distance_m, compareActivity.total_distance_m),
    });

    // Elevation Gain
    rows.push({
      label: "Elevation Gain",
      baseValue: formatElevation(baseActivity.elevation_gain_m),
      compareValue: formatElevation(compareActivity.elevation_gain_m),
      baseRaw: baseActivity.elevation_gain_m,
      compareRaw: compareActivity.elevation_gain_m,
      delta: formatDelta(
        baseActivity.elevation_gain_m,
        compareActivity.elevation_gain_m,
        (v) => formatElevation(Math.abs(v))
      ),
      winner: getWinner(baseActivity.elevation_gain_m, compareActivity.elevation_gain_m),
    });

    // Avg Speed
    rows.push({
      label: "Avg Speed",
      baseValue: formatSpeed(baseActivity.avg_speed_mps),
      compareValue: formatSpeed(compareActivity.avg_speed_mps),
      baseRaw: baseActivity.avg_speed_mps,
      compareRaw: compareActivity.avg_speed_mps,
      delta: formatDelta(
        baseActivity.avg_speed_mps,
        compareActivity.avg_speed_mps,
        (v) => formatSpeed(Math.abs(v))
      ),
      winner: getWinner(baseActivity.avg_speed_mps, compareActivity.avg_speed_mps),
    });

    // Max Speed
    rows.push({
      label: "Max Speed",
      baseValue: formatSpeed(baseActivity.max_speed_mps),
      compareValue: formatSpeed(compareActivity.max_speed_mps),
      baseRaw: baseActivity.max_speed_mps,
      compareRaw: compareActivity.max_speed_mps,
      delta: formatDelta(
        baseActivity.max_speed_mps,
        compareActivity.max_speed_mps,
        (v) => formatSpeed(Math.abs(v))
      ),
      winner: getWinner(baseActivity.max_speed_mps, compareActivity.max_speed_mps),
    });

    // Avg HR (only if both have data)
    if (baseActivity.avg_hr_bpm !== null || compareActivity.avg_hr_bpm !== null) {
      rows.push({
        label: "Avg HR",
        baseValue: baseActivity.avg_hr_bpm !== null ? `${baseActivity.avg_hr_bpm} bpm` : "—",
        compareValue: compareActivity.avg_hr_bpm !== null ? `${compareActivity.avg_hr_bpm} bpm` : "—",
        baseRaw: baseActivity.avg_hr_bpm,
        compareRaw: compareActivity.avg_hr_bpm,
        delta: formatDelta(
          baseActivity.avg_hr_bpm,
          compareActivity.avg_hr_bpm,
          (v) => `${Math.abs(Math.round(v))} bpm`
        ),
        winner: null, // HR isn't a "winner" metric - depends on context
      });
    }

    // Max HR (only if both have data)
    if (baseActivity.max_hr_bpm !== null || compareActivity.max_hr_bpm !== null) {
      rows.push({
        label: "Max HR",
        baseValue: baseActivity.max_hr_bpm !== null ? `${baseActivity.max_hr_bpm} bpm` : "—",
        compareValue: compareActivity.max_hr_bpm !== null ? `${compareActivity.max_hr_bpm} bpm` : "—",
        baseRaw: baseActivity.max_hr_bpm,
        compareRaw: compareActivity.max_hr_bpm,
        delta: formatDelta(
          baseActivity.max_hr_bpm,
          compareActivity.max_hr_bpm,
          (v) => `${Math.abs(Math.round(v))} bpm`
        ),
        winner: null, // HR isn't a "winner" metric
      });
    }

    // Avg Power (only if either has data)
    if (baseActivity.avg_power_w !== null || compareActivity.avg_power_w !== null) {
      rows.push({
        label: "Avg Power",
        baseValue: baseActivity.avg_power_w !== null ? `${Math.round(baseActivity.avg_power_w)} W` : "—",
        compareValue: compareActivity.avg_power_w !== null ? `${Math.round(compareActivity.avg_power_w)} W` : "—",
        baseRaw: baseActivity.avg_power_w,
        compareRaw: compareActivity.avg_power_w,
        delta: formatDelta(
          baseActivity.avg_power_w,
          compareActivity.avg_power_w,
          (v) => `${Math.abs(Math.round(v))} W`
        ),
        winner: getWinner(baseActivity.avg_power_w, compareActivity.avg_power_w),
      });
    }

    // NP (only if either has data)
    if (baseActivity.np_power_w !== null || compareActivity.np_power_w !== null) {
      rows.push({
        label: "Normalized Power",
        baseValue: baseActivity.np_power_w !== null ? `${Math.round(baseActivity.np_power_w)} W` : "—",
        compareValue: compareActivity.np_power_w !== null ? `${Math.round(compareActivity.np_power_w)} W` : "—",
        baseRaw: baseActivity.np_power_w,
        compareRaw: compareActivity.np_power_w,
        delta: formatDelta(
          baseActivity.np_power_w,
          compareActivity.np_power_w,
          (v) => `${Math.abs(Math.round(v))} W`
        ),
        winner: getWinner(baseActivity.np_power_w, compareActivity.np_power_w),
      });
    }

    // TSS (only if either has data)
    if (baseActivity.tss !== null || compareActivity.tss !== null) {
      rows.push({
        label: "TSS",
        baseValue: baseActivity.tss !== null ? `${Math.round(baseActivity.tss)}` : "—",
        compareValue: compareActivity.tss !== null ? `${Math.round(compareActivity.tss)}` : "—",
        baseRaw: baseActivity.tss,
        compareRaw: compareActivity.tss,
        delta: formatDelta(
          baseActivity.tss,
          compareActivity.tss,
          (v) => `${Math.abs(Math.round(v))}`
        ),
        winner: getWinner(baseActivity.tss, compareActivity.tss),
      });
    }

    // IF (only if either has data)
    if (baseActivity.intensity_factor !== null || compareActivity.intensity_factor !== null) {
      rows.push({
        label: "Intensity Factor",
        baseValue: baseActivity.intensity_factor !== null ? baseActivity.intensity_factor.toFixed(2) : "—",
        compareValue: compareActivity.intensity_factor !== null ? compareActivity.intensity_factor.toFixed(2) : "—",
        baseRaw: baseActivity.intensity_factor,
        compareRaw: compareActivity.intensity_factor,
        delta: formatDelta(
          baseActivity.intensity_factor,
          compareActivity.intensity_factor,
          (v) => Math.abs(v).toFixed(2)
        ),
        winner: getWinner(baseActivity.intensity_factor, compareActivity.intensity_factor),
      });
    }

    // Final Time Gap from comparison (if available)
    if (comparison?.gap_series && comparison.gap_series.length > 0) {
      const finalGap = comparison.gap_series[comparison.gap_series.length - 1].gap_s;
      rows.push({
        label: "Final Time Gap",
        baseValue: finalGap < 0 ? formatGap(Math.abs(finalGap)) + " ahead" : "—",
        compareValue: finalGap > 0 ? formatGap(finalGap) + " ahead" : "—",
        baseRaw: -finalGap, // Negative gap means base is ahead
        compareRaw: finalGap,
        delta: formatGap(finalGap),
        winner: finalGap < -0.5 ? "base" : finalGap > 0.5 ? "compare" : "tie",
      });
    }

    return rows;
  }, [baseActivity, compareActivity, comparison]);

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">
          Stats Comparison
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50">
              <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                Metric
              </th>
              <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  {baseActivity.title || "Base"}
                </div>
              </th>
              <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                <div className="flex items-center justify-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-amber-500" />
                  {compareActivity.title || "Compare"}
                </div>
              </th>
              <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                Delta
              </th>
            </tr>
          </thead>
          <tbody>
            {stats.map((stat, idx) => (
              <tr
                key={stat.label}
                className={`border-t border-border ${
                  idx % 2 === 0 ? "" : "bg-muted/25"
                }`}
              >
                <td className="px-4 py-2 font-medium text-foreground">
                  {stat.label}
                </td>
                <td className="px-4 py-2 text-center">
                  <span
                    className={`${
                      stat.winner === "base"
                        ? "text-success font-semibold"
                        : "text-muted-foreground"
                    }`}
                  >
                    {stat.baseValue || "—"}
                    {stat.winner === "base" && (
                      <span className="ml-1 text-success">✓</span>
                    )}
                  </span>
                </td>
                <td className="px-4 py-2 text-center">
                  <span
                    className={`${
                      stat.winner === "compare"
                        ? "text-success font-semibold"
                        : "text-muted-foreground"
                    }`}
                  >
                    {stat.compareValue || "—"}
                    {stat.winner === "compare" && (
                      <span className="ml-1 text-success">✓</span>
                    )}
                  </span>
                </td>
                <td className="px-4 py-2 text-center text-muted-foreground">
                  {stat.delta || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Apply 100m rolling average smoothing to gap data
function smoothGapData(
  gapSeries: GapPoint[],
  elevationByDistance: Map<number, number>
): GapChartPoint[] {
  const windowMeters = 100;
  
  return gapSeries.map((point) => {
    const windowStart = point.distance_m - windowMeters / 2;
    const windowEnd = point.distance_m + windowMeters / 2;
    
    // Find points within the window
    const windowPoints = gapSeries.filter(
      (p) => p.distance_m >= windowStart && p.distance_m <= windowEnd
    );
    
    // Average the gap values
    const avgGap = windowPoints.reduce((sum, p) => sum + p.gap_s, 0) / windowPoints.length;
    
    // Find nearest elevation
    let nearestElev: number | null = null;
    let minDist = Infinity;
    for (const [dist, elev] of elevationByDistance) {
      const d = Math.abs(dist - point.distance_m);
      if (d < minDist) {
        minDist = d;
        nearestElev = elev;
      }
    }
    
    return {
      distance_m: point.distance_m,
      gap_s: avgGap,
      elevation_m: nearestElev,
    };
  });
}

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const baseIdParam = searchParams.get("base");
  const compareIdParam = searchParams.get("compare");
  
  const [baseActivity, setBaseActivity] = useState<Activity | null>(null);
  const [compareActivity, setCompareActivity] = useState<Activity | null>(null);
  const [baseGeojson, setBaseGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [compareGeojson, setCompareGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [sameRouteData, setSameRouteData] = useState<SameRouteResponse | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);
  
  // Track if we've already loaded from URL
  const loadedBaseFromUrl = useRef(false);
  const loadedCompareFromUrl = useRef(false);

  // Resizable map with separate localStorage key for Compare page
  const {
    height: mapHeight,
    isResizing,
    startResizeHeight,
  } = useResizableMap({
    storageKey: "compare-page",
    defaultHeight: 250,
    minHeight: 150,
    maxHeight: 400,
    defaultWidthPercent: 40,
    minWidthPercent: 25,
    maxWidthPercent: 60,
  });

  // Load base activity from URL param on mount
  useEffect(() => {
    if (baseIdParam && !loadedBaseFromUrl.current) {
      loadedBaseFromUrl.current = true;
      setLoading(true);
      Promise.all([fetchActivity(baseIdParam), fetchActivityRecords(baseIdParam), fetchSameRouteActivities(baseIdParam)])
        .then(([activity, geojson, sameRoute]) => {
          setBaseActivity(activity);
          setBaseGeojson(geojson);
          setSameRouteData(sameRoute);
        })
        .catch((e) => {
          console.error("[ComparePage] Failed to load base activity from URL:", e);
        })
        .finally(() => setLoading(false));
    }
  }, [baseIdParam]);

  // Load compare activity from URL param on mount
  useEffect(() => {
    if (compareIdParam && !loadedCompareFromUrl.current && baseActivity) {
      loadedCompareFromUrl.current = true;
      Promise.all([
        fetchActivity(compareIdParam),
        fetchActivityRecords(compareIdParam),
        fetchComparison(baseActivity.id, compareIdParam),
      ])
        .then(([activity, geojson, comp]) => {
          setCompareActivity(activity);
          setCompareGeojson(geojson);
          setComparison(comp);
        })
        .catch((e) => {
          console.error("[ComparePage] Failed to load compare activity from URL:", e);
        });
    }
  }, [compareIdParam, baseActivity]);

  const updateSearchParams = (base: Activity | null, compare: Activity | null) => {
    const params: Record<string, string> = {};
    if (base) params.base = base.id;
    if (compare) params.compare = compare.id;
    setSearchParams(params);
  };

  const handleBaseSelect = (activity: Activity | null) => {
    setBaseActivity(activity);
    setBaseGeojson(null);
    setSameRouteData(null);
    setCompareActivity(null);
    setCompareGeojson(null);
    setComparison(null);
    
    if (activity) {
      setLoading(true);
      Promise.all([fetchActivityRecords(activity.id), fetchSameRouteActivities(activity.id)])
        .then(([geojson, sameRoute]) => {
          setBaseGeojson(geojson);
          setSameRouteData(sameRoute);
        })
        .catch((e) => {
          console.error("[ComparePage] Failed to load base activity data:", e);
        })
        .finally(() => setLoading(false));
      setSearchParams({ base: activity.id.toString() });
    } else {
      setSearchParams({});
    }
  };

  const handleCompareSelect = (activity: Activity | null) => {
    setCompareGeojson(null);
    setComparison(null);
    
    if (activity && baseActivity) {
      // Set compareActivity to null initially to show loading state
      // This prevents rendering with partial activity data
      setCompareActivity(null);
      
      Promise.all([
        fetchActivity(activity.id),  // Fetch full activity details
        fetchActivityRecords(activity.id),
        fetchComparison(baseActivity.id, activity.id),
      ])
        .then(([fullActivity, geojson, comp]) => {
          setCompareActivity(fullActivity);  // Use full activity with all fields
          setCompareGeojson(geojson);
          setComparison(comp);
        })
        .catch((e) => {
          console.error("[ComparePage] Failed to load compare activity data:", e);
        });
      updateSearchParams(baseActivity, activity);
    } else {
      setCompareActivity(null);
      updateSearchParams(baseActivity, null);
    }
  };

  const handleSwap = () => {
    const tempActivity = baseActivity;
    const tempGeojson = baseGeojson;
    
    // When swapping, we need to reload same-route data for the new base
    if (compareActivity) {
      setLoading(true);
      fetchSameRouteActivities(compareActivity.id)
        .then((sameRoute) => {
          setBaseActivity(compareActivity);
          setBaseGeojson(compareGeojson);
          setSameRouteData(sameRoute);
          setCompareActivity(tempActivity);
          setCompareGeojson(tempGeojson);
          updateSearchParams(compareActivity, tempActivity);
        })
        .catch((e) => {
          console.error("[ComparePage] Failed to swap activities:", e);
        })
        .finally(() => setLoading(false));
    }
  };

  // Extract positions for map
  const basePositions = useMemo(() => {
    if (!baseGeojson) return [];
    return baseGeojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
  }, [baseGeojson]);

  const comparePositions = useMemo(() => {
    if (!compareGeojson) return [];
    return compareGeojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
  }, [compareGeojson]);

  // Get same-route activity IDs for filtering
  const sameRouteActivityIds = useMemo(() => {
    if (!sameRouteData) return [];
    return sameRouteData.activities.map((a) => a.id);
  }, [sameRouteData]);

  const hasSameRouteActivities = sameRouteActivityIds.length > 0;

  // Build elevation lookup from base geojson
  const elevationByDistance = useMemo(() => {
    const map = new Map<number, number>();
    if (!baseGeojson) return map;
    for (const f of baseGeojson.features) {
      if (f.properties.altitude_m !== null) {
        map.set(f.properties.distance_m, f.properties.altitude_m);
      }
    }
    return map;
  }, [baseGeojson]);

  // Smoothed gap chart data
  const gapChartData = useMemo((): GapChartPoint[] => {
    if (!comparison?.gap_series || comparison.gap_series.length === 0) return [];
    return smoothGapData(comparison.gap_series, elevationByDistance);
  }, [comparison, elevationByDistance]);

  // Position lookup by distance for hover sync
  const posByDist = useMemo(() => {
    if (!baseGeojson) return [];
    return baseGeojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => ({
        distance_m: f.properties.distance_m,
        pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
      }));
  }, [baseGeojson]);

  const findPositionByDistance = (distance_m: number): [number, number] | null => {
    if (posByDist.length === 0) return null;
    let closest = posByDist[0];
    let minDiff = Math.abs(closest.distance_m - distance_m);
    for (const p of posByDist) {
      const diff = Math.abs(p.distance_m - distance_m);
      if (diff < minDiff) {
        minDiff = diff;
        closest = p;
      }
    }
    return closest.pos;
  };

  // Build color-coded map segments based on gap data
  const coloredSegments = useMemo(() => {
    if (!comparison?.gap_series || comparison.gap_series.length < 2 || posByDist.length < 2) {
      return [];
    }

    const gapSeries = comparison.gap_series;
    const segments: { positions: [number, number][]; color: string }[] = [];

    for (let i = 0; i < gapSeries.length - 1; i++) {
      const distStart = gapSeries[i].distance_m;
      const distEnd = gapSeries[i + 1].distance_m;
      const color = gapColor(gapSeries[i].gap_s);

      const pointsInSegment: [number, number][] = [];
      for (const p of posByDist) {
        if (p.distance_m >= distStart && p.distance_m <= distEnd) {
          pointsInSegment.push(p.pos);
        }
      }
      if (pointsInSegment.length >= 2) {
        segments.push({ positions: pointsInSegment, color });
      }
    }

    return segments;
  }, [comparison, posByDist]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleChartHover = (state: any) => {
    if (state?.activePayload?.[0]?.payload) {
      const point = state.activePayload[0].payload as GapChartPoint;
      const pos = findPositionByDistance(point.distance_m);
      setHoveredPosition(pos);
    }
  };

  const handleChartLeave = () => {
    setHoveredPosition(null);
  };

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Page Header */}
      <div className="flex-shrink-0 p-8 pb-0">
        <h1 className="text-3xl font-bold text-foreground mb-2">Compare Activities</h1>
        <p className="text-muted-foreground">Compare performance metrics between two activities</p>
      </div>

      {/* Sticky map */}
      {basePositions.length > 0 && (
        <div className="flex-shrink-0 px-8 pt-6 pb-0">
          <ResizableMap
            positions={basePositions}
            coloredSegments={coloredSegments.length > 0 ? coloredSegments : undefined}
            otherPositions={comparePositions.length > 0 && coloredSegments.length === 0 ? comparePositions : null}
            hoveredPosition={hoveredPosition}
            height={mapHeight}
            onResizeStart={startResizeHeight}
            isResizing={isResizing}
          />
        </div>
      )}

      {/* Control bar with activity selectors */}
      <div className="flex-shrink-0 px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Base activity selector */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 rounded-full bg-primary" />
              <label className="text-sm font-medium text-muted-foreground">Base Activity</label>
            </div>
            <ActivitySelector
              selectedId={baseActivity?.id ?? null}
              onSelect={handleBaseSelect}
              excludeIds={compareActivity ? [compareActivity.id] : []}
              label=""
              placeholder="Select the base ride..."
              className="border-2 border-primary/30 focus-within:ring-2 focus-within:ring-primary/50"
            />
            {baseActivity && (
              <Link
                to={`/activities/${baseActivity.id}`}
                className="inline-flex items-center mt-2 text-sm text-primary hover:underline"
              >
                <span className="w-2 h-2 rounded-full bg-primary mr-2" />
                {baseActivity.title || "Untitled"} →
              </Link>
            )}
          </div>
          
          {/* Compare activity selector */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <label className="text-sm font-medium text-muted-foreground">Compare With</label>
            </div>
            {baseActivity ? (
              hasSameRouteActivities ? (
                <>
                  <ActivitySelector
                    selectedId={compareActivity?.id ?? null}
                    onSelect={handleCompareSelect}
                    filterIds={sameRouteActivityIds}
                    excludeIds={[baseActivity.id]}
                    label=""
                    placeholder="Select ride to compare..."
                    className="border-2 border-border focus-within:ring-2 focus-within:ring-blue-500/50"
                  />
                  {compareActivity && (
                    <Link
                      to={`/activities/${compareActivity.id}`}
                      className="inline-flex items-center mt-2 text-sm text-blue-500 hover:underline"
                    >
                      <span className="w-2 h-2 rounded-full bg-blue-500 mr-2" />
                      {compareActivity.title || "Untitled"} →
                    </Link>
                  )}
                </>
              ) : (
                <div className="px-4 py-3 bg-muted rounded-xl border-2 border-border text-muted-foreground text-sm">
                  No other rides on this route yet. Select a different base activity.
                </div>
              )
            ) : (
              <div className="px-4 py-3 bg-muted rounded-xl border-2 border-border text-muted-foreground text-sm">
                Select a base activity first
              </div>
            )}
          </div>
        </div>

        {/* Swap button */}
        {baseActivity && compareActivity && (
          <div className="flex justify-center mt-6">
            <button
              onClick={handleSwap}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast disabled:opacity-50"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              Swap Activities
            </button>
          </div>
        )}
      </div>

      {/* Comparison content area */}
      <div className="flex-1 min-h-0 px-8 pb-8 overflow-y-auto">
        {/* Suggested Comparisons - shown when base activity is selected but no comparison yet */}
        {baseActivity && !compareActivity && sameRouteData && (
          <div className="mb-8">
            <h3 className="text-lg font-semibold mb-2">Suggested Comparisons</h3>
            <p className="text-sm text-muted-foreground mb-4">Activities similar to your selected ride</p>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* Same Route suggestions */}
              {sameRouteData.activities.slice(0, 3).map((activity) => (
                <div
                  key={activity.id}
                  onClick={() => handleCompareSelect(activity)}
                  className="bg-card rounded-xl border border-border p-4 card-hover cursor-pointer hover:border-primary/50 transition-all duration-300"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-16 h-12 bg-muted/30 rounded-lg overflow-hidden flex-shrink-0 flex items-center justify-center">
                      <svg className="w-8 h-8 text-primary/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                      </svg>
                    </div>
                    <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full flex items-center gap-1">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                      </svg>
                      Same Route
                    </span>
                  </div>
                  <h4 className="font-medium mb-1 truncate">
                    {activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: "short", month: "short", day: "numeric" })}
                  </h4>
                  <p className="text-sm text-muted-foreground mb-3">
                    {formatRelativeTime(activity.started_at)}
                  </p>
                  <div className="flex gap-3 text-xs text-muted-foreground">
                    <div>{formatDistance(activity.total_distance_m)}</div>
                    <div>{formatTime(activity.moving_time_s)}</div>
                    <div>{activity.avg_power_w ? `${Math.round(activity.avg_power_w)}W` : "—"}</div>
                  </div>
                </div>
              ))}
              
              {/* If no same-route activities */}
              {sameRouteData.activities.length === 0 && (
                <div className="col-span-full text-center py-8 text-muted-foreground">
                  <p>No same-route activities found. Try selecting a different base activity.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {/* Activity summary skeletons */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-card rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Skeleton className="w-3 h-3 rounded-full" />
                  <Skeleton className="h-3 w-12" />
                </div>
                <Skeleton className="h-6 w-48 mb-1" />
                <Skeleton className="h-4 w-32" />
              </div>
              <div className="bg-card rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Skeleton className="w-3 h-3 rounded-full" />
                  <Skeleton className="h-3 w-16" />
                </div>
                <Skeleton className="h-6 w-48 mb-1" />
                <Skeleton className="h-4 w-32" />
              </div>
            </div>
            {/* Comparison chart skeleton */}
            <div className="bg-card rounded-lg border border-border p-4">
              <Skeleton className="h-5 w-40 mb-4" />
              <ChartSkeleton height="h-64" />
            </div>
          </div>
        ) : baseActivity && compareActivity ? (
          <div className="space-y-4">
            {/* Activities summary cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-card rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-3 h-3 rounded-full bg-indigo-500" />
                  <span className="text-xs font-medium text-primary uppercase tracking-wide">
                    Base
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-foreground">
                  {baseActivity.title || "Untitled"}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {formatActivityDate(baseActivity.started_at, baseActivity.utc_offset_minutes, {
                    weekday: "short",
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </p>
              </div>
              <div className="bg-card rounded-lg border border-border p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-3 h-3 rounded-full bg-amber-500" />
                  <span className="text-xs font-medium text-warning uppercase tracking-wide">
                    Compare
                  </span>
                </div>
                <h3 className="text-lg font-semibold text-foreground">
                  {compareActivity.title || "Untitled"}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {formatActivityDate(compareActivity.started_at, compareActivity.utc_offset_minutes, {
                    weekday: "short",
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </p>
              </div>
            </div>

            {/* Gap Chart */}
            {comparison?.comparable && gapChartData.length > 0 && (
              <ChartErrorBoundary>
                <div className="bg-card rounded-lg border border-border p-4">
                  <h3 className="text-sm font-medium text-foreground mb-3">
                    Time Gap vs Distance
                  </h3>
                  <div style={{ height: 350 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart
                        data={gapChartData}
                        onMouseMove={handleChartHover}
                        onMouseLeave={handleChartLeave}
                        margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
                        <XAxis
                          dataKey="distance_m"
                          tickFormatter={formatDistanceKm}
                          stroke="#9ca3af"
                          fontSize={12}
                        />
                        <YAxis
                          yAxisId="gap"
                          stroke="#9ca3af"
                          fontSize={12}
                          tickFormatter={(v) => `${v > 0 ? "+" : ""}${v}s`}
                          domain={["auto", "auto"]}
                        />
                        <YAxis
                          yAxisId="elevation"
                          orientation="right"
                          stroke="#9ca3af"
                          fontSize={12}
                          tickFormatter={(v) => `${Math.round(v)}m`}
                          domain={["dataMin - 50", "dataMax + 50"]}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: "#1f2937",
                            border: "1px solid #374151",
                            borderRadius: "0.375rem",
                            color: "#f9fafb",
                          }}
                          formatter={(value, name) => {
                            if (name === "gap_s") {
                              const gap = value as number;
                              const label = gap < 0 ? "ahead" : "behind";
                              return [`${formatGap(gap)} ${label}`, "Gap"];
                            }
                            if (name === "elevation_m") {
                              return [`${Math.round(value as number)} m`, "Elevation"];
                            }
                            return [value, name];
                          }}
                          labelFormatter={(label) => formatDistanceKm(label as number)}
                        />
                        <ReferenceLine y={0} yAxisId="gap" stroke="#6366f1" strokeDasharray="3 3" />
                        
                        {/* Elevation as filled area background */}
                        <Area
                          type="monotone"
                          dataKey="elevation_m"
                          yAxisId="elevation"
                          fill="#10b981"
                          fillOpacity={0.15}
                          stroke="#10b981"
                          strokeWidth={1}
                          strokeOpacity={0.5}
                        />
                        
                        {/* Gap line */}
                        <Line
                          type="monotone"
                          dataKey="gap_s"
                          yAxisId="gap"
                          stroke="#f59e0b"
                          strokeWidth={2}
                          dot={false}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="flex items-center justify-center gap-6 mt-3 text-xs text-muted-foreground">
                    <div className="flex items-center gap-1">
                      <span className="w-3 h-3 rounded-full bg-green-500" />
                      <span>Faster (ahead)</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="w-3 h-3 rounded-full bg-indigo-500" />
                      <span>Even</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="w-3 h-3 rounded-full bg-red-500" />
                      <span>Slower (behind)</span>
                    </div>
                  </div>
                </div>
              </ChartErrorBoundary>
            )}

{/* Power Comparison Chart - Collapsible */}
            <PowerComparisonChart
              baseGeojson={baseGeojson}
              compareGeojson={compareGeojson}
              baseActivity={baseActivity}
              compareActivity={compareActivity}
              onHover={handleChartHover}
              onLeave={handleChartLeave}
            />

{/* Stats Comparison Table */}
            <StatsTable
              baseActivity={baseActivity}
              compareActivity={compareActivity}
              comparison={comparison}
            />
          </div>
        ) : !baseActivity ? (
          /* Improved empty state with info panels */
          <div className="bg-card border border-border rounded-xl p-12">
            <div className="max-w-3xl mx-auto text-center">
              <svg className="w-24 h-24 text-muted-foreground/50 mx-auto mb-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4"/>
              </svg>
              <h2 className="text-2xl font-bold mb-3 text-foreground">Select Two Activities to Compare</h2>
              <p className="text-muted-foreground mb-8">Choose a base activity above, then select another to compare performance, routes, and training load.</p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-left max-w-2xl mx-auto">
                <div className="bg-muted/30 rounded-lg p-5 border-l-4 border-primary">
                  <h3 className="font-semibold mb-2 flex items-center gap-2 text-foreground">
                    <div className="w-2 h-2 rounded-full bg-primary" />
                    What You Can Compare
                  </h3>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    <li className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>
                      <span>Power profiles and zones</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>
                      <span>Heart rate distribution</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7"/></svg>
                      <span>Speed and elevation profiles</span>
                    </li>
                  </ul>
                </div>
                
                <div className="bg-muted/30 rounded-lg p-5 border-l-4 border-blue-500">
                  <h3 className="font-semibold mb-2 flex items-center gap-2 text-foreground">
                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                    Comparison Tips
                  </h3>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    <li className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                      <span>Same route on different days</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                      <span>Track fitness improvements</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <svg className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                      <span>Different pacing strategies</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* Base selected but no compare activity yet - show simple message */
          <div className="flex items-center justify-center h-64 bg-card rounded-xl border border-border">
            <p className="text-muted-foreground">Select an activity to compare with from the suggestions above.</p>
          </div>
        )}
      </div>
    </div>
  );
}
