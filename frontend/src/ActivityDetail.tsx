import { Link } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
  ReferenceArea,
} from "recharts";
import type { WbalResponse, WbalPoint } from "./api";
import { formatDistance, formatTime, formatElevation, formatSpeed } from "./format";
import type { UnitSystem } from "./format";
import { resampleByDistance } from "./resampler";
import { ErrorDisplay } from "./ErrorDisplay";
import { ResizableMap } from "./components/ResizableMap";
import { useResizableMap } from "./hooks/useResizableMap";
import { useActivityDetail } from "./hooks/useActivityDetail";
import { ChartExpandModal } from "./components/ChartExpandModal";
import { ActivityPowerCurve } from "./components/ActivityPowerCurve";
import { ChartErrorBoundary } from "./components/ErrorBoundary";
import { POWER_ZONE_COLORS, HR_ZONE_COLORS } from "./constants";
import { Skeleton } from "@/components/ui/skeleton";

function ActivityDetailLoadingSkeleton() {
  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Back button and header */}
        <Skeleton className="h-8 w-20" />
        <div className="space-y-2">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-48" />
        </div>
        
        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-card rounded-lg border border-border p-4">
              <Skeleton className="h-3 w-16 mb-2" />
              <Skeleton className="h-7 w-20" />
            </div>
          ))}
        </div>
        
        {/* Map */}
        <div className="bg-card rounded-lg border border-border p-4">
          <Skeleton className="h-5 w-16 mb-3" />
          <div className="h-80 bg-muted rounded-lg flex items-center justify-center">
            <svg className="w-12 h-12 text-muted-foreground/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
        </div>
        
        {/* Chart */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center justify-between mb-3">
            <Skeleton className="h-5 w-32" />
            <div className="flex gap-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-8 w-16 rounded" />
              ))}
            </div>
          </div>
          <div className="h-64 bg-muted rounded flex items-end justify-around p-4 gap-1">
            {[40, 55, 35, 60, 45, 70, 50, 65, 45, 75, 55, 80, 60, 50, 70].map((h, i) => (
              <Skeleton key={i} className="flex-1 rounded-t" style={{ height: `${h}%` }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

interface ChartConfig {
  key: string;
  label: string;
  unit: string;
  color: string;
  dataKey: string;
}

const CHARTS: ChartConfig[] = [
  { key: "speed", label: "Speed", unit: "m/s", color: "#6366f1", dataKey: "speed_mps" },
  { key: "hr", label: "Heart Rate", unit: "bpm", color: "#ef4444", dataKey: "hr_bpm" },
  { key: "power", label: "Power", unit: "W", color: "#f59e0b", dataKey: "power_w" },
  { key: "elevation", label: "Elevation", unit: "m", color: "#10b981", dataKey: "altitude_m" },
];

interface Props {
  activityId: string;
  onBack: () => void;
  unitSystem?: UnitSystem;
}

export function ActivityDetail({ activityId, onBack, unitSystem = "metric" }: Props) {
  // Use the custom hook for all activity data management
  const {
    loading,
    error,
    setError,
    activity,
    geojson,
    sameRoute,
    wbalData,
    records,
    timestamps,
    firstTs,
    positions,
    ftpWatts,
    lthrBpm,
    axisModes,
    toggleAxis,
    hoveredPosition,
    setHoveredPosition,
    findPositionByElapsed,
    findPositionByDistance,
    isEditingTitle,
    setIsEditingTitle,
    editedTitle,
    setEditedTitle,
    saveTitle,
    isGeneratingTitle,
    generateTitle,
    expandedChart,
    setExpandedChart,
  } = useActivityDetail(activityId);

  // Responsive layout hooks for resizable map
  const {
    height: mapHeight,
    isResizing,
    startResizeHeight,
  } = useResizableMap({
    storageKey: "activity-detail",
    defaultHeight: 250,
    minHeight: 150,
    maxHeight: 400,
    defaultWidthPercent: 40,
    minWidthPercent: 25,
    maxWidthPercent: 60,
  });

  const handleChartLeave = () => {
    setHoveredPosition(null);
  };

  if (error) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-6xl mx-auto">
          <ErrorDisplay error={error} context="loading activity" />
        </div>
      </div>
    );
  }

  if (loading || !activity || !geojson) {
    return <ActivityDetailLoadingSkeleton />;
  }

  interface ChartDataPoint {
    distance_m: number;
    elapsed: number;
    speed_mps: number | null;
    hr_bpm: number | null;
    power_w: number | null;
    altitude_m: number | null;
  }

  function formatElapsedTime(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function formatDistanceAxis(meters: number): string {
    if (meters >= 1000) {
      const km = meters / 1000;
      return km % 1 === 0 ? `${km.toFixed(0)} km` : `${km.toFixed(1)} km`;
    }
    return `${meters.toFixed(0)} m`;
  }

  // Heckbert's "nice numbers" algorithm from Graphics Gems
  // Returns a "nice" number approximately equal to range
  // If round is true, round to nearest nice number, otherwise ceiling
  function niceNum(range: number, round: boolean): number {
    const exponent = Math.floor(Math.log10(range));
    const fraction = range / Math.pow(10, exponent);
    let niceFraction: number;

    if (round) {
      if (fraction < 1.5) niceFraction = 1;
      else if (fraction < 3) niceFraction = 2;
      else if (fraction < 7) niceFraction = 5;
      else niceFraction = 10;
    } else {
      if (fraction <= 1) niceFraction = 1;
      else if (fraction <= 2) niceFraction = 2;
      else if (fraction <= 5) niceFraction = 5;
      else niceFraction = 10;
    }

    return niceFraction * Math.pow(10, exponent);
  }

  // Generate nice tick values using Heckbert's algorithm
  function getNiceTicks(min: number, max: number, maxTicks: number = 8): number[] {
    if (max === min) return [min];
    
    const range = niceNum(max - min, false);
    const tickSpacing = niceNum(range / (maxTicks - 1), true);
    const niceLowerBound = Math.floor(min / tickSpacing) * tickSpacing;
    const niceUpperBound = Math.ceil(max / tickSpacing) * tickSpacing;
    
    const ticks: number[] = [];
    for (let tick = niceLowerBound; tick <= niceUpperBound + tickSpacing * 0.5; tick += tickSpacing) {
      // Round to avoid floating point issues
      const roundedTick = Math.round(tick * 1e10) / 1e10;
      if (roundedTick >= min - tickSpacing * 0.1 && roundedTick <= max + tickSpacing * 0.1) {
        ticks.push(roundedTick);
      }
    }
    return ticks;
  }

  // For time, use nice intervals that make sense (30s, 1m, 2m, 5m, 10m, etc.)
  function getNiceTimeTicks(maxSeconds: number, maxTicks: number = 10): number[] {
    // Nice time intervals in seconds - more granular options
    const niceIntervals = [10, 15, 30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600];
    const idealInterval = maxSeconds / maxTicks;
    const interval = niceIntervals.find(i => i >= idealInterval) || niceIntervals[niceIntervals.length - 1];
    
    const ticks: number[] = [];
    for (let t = 0; t <= maxSeconds; t += interval) {
      ticks.push(t);
    }
    return ticks;
  }

  function getChartData(chart: ChartConfig) {
    const mode = axisModes[chart.key];
    if (mode === "distance") {
      const resampled = resampleByDistance(records);
      const data: ChartDataPoint[] = resampled.map((r, i) => ({
        distance_m: r.distance_m,
        elapsed: i,
        speed_mps: r.speed_mps,
        hr_bpm: r.hr_bpm,
        power_w: r.power_w,
        altitude_m: r.altitude_m,
      }));
      const maxDistance = Math.max(...data.map(d => d.distance_m));
      return {
        data,
        xKey: "distance_m" as const,
        xLabel: "Distance",
        tickFormatter: formatDistanceAxis,
        ticks: getNiceTicks(0, maxDistance, 10),
      };
    }
    const data: ChartDataPoint[] = timestamps.map((ts, i) => ({
      distance_m: records[i].distance_m,
      elapsed: ts - firstTs,
      speed_mps: records[i].speed_mps,
      hr_bpm: records[i].hr_bpm,
      power_w: records[i].power_w,
      altitude_m: records[i].altitude_m,
    }));
    const maxTime = Math.max(...data.map(d => d.elapsed));
    return {
      data,
      xKey: "elapsed" as const,
      xLabel: "Time",
      tickFormatter: formatElapsedTime,
      ticks: getNiceTimeTicks(maxTime, 10),
    };
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1">
            {isEditingTitle ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="flex-1 px-3 py-2 text-lg font-bold text-foreground bg-input border border-input-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      saveTitle(editedTitle).catch((err) => setError(err));
                    } else if (e.key === "Escape") {
                      setIsEditingTitle(false);
                    }
                  }}
                />
                <button
                  onClick={() => {
                    saveTitle(editedTitle).catch((err) => setError(err));
                  }}
                  className="px-3 py-2 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/80"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsEditingTitle(false)}
                  className="px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold text-foreground">
                    {activity.title || new Date(activity.started_at).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                  </h1>
                  {activity.title_source === "pending" && (
                    <button
                      onClick={() => {
                        generateTitle().catch((err) => setError(err));
                      }}
                      disabled={isGeneratingTitle}
                      className="p-1 text-primary hover:text-primary/80 disabled:opacity-50"
                      title="Generate location-based title from GPS"
                    >
                      {isGeneratingTitle ? (
                        <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      )}
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setEditedTitle(activity.title || "");
                      setIsEditingTitle(true);
                    }}
                    className="p-1 text-muted-foreground hover:text-foreground"
                    title="Edit title"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                </div>
                {/* Date/time subtitle */}
                <div className="flex items-center gap-4 text-base text-muted-foreground mt-1">
                  <span className="flex items-center gap-1.5">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    {new Date(activity.started_at).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {new Date(activity.started_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })}
                    {" - "}
                    {new Date(new Date(activity.started_at).getTime() + (activity.elapsed_time_s * 1000)).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })}
                    {" "}
                    <span className="text-muted-foreground/70">({formatTime(activity.elapsed_time_s)})</span>
                  </span>
                </div>
              </>
            )}
          </div>
          
          {/* Action buttons - right aligned with equal width */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={onBack}
              className="w-28 px-4 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted transition-fast flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back
            </button>
            <Link
              to={`/analyze?activity=${activityId}`}
              className="w-28 px-4 py-2 text-sm font-medium text-primary bg-primary/10 border border-primary/30 rounded-lg hover:bg-primary/20 transition-fast flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
              Analyze
            </Link>
            {sameRoute && sameRoute.route_id !== null && sameRoute.activities.length > 0 && (
              <Link
                to={`/compare?base=${activityId}`}
                className="w-28 px-4 py-2 text-sm font-medium text-warning bg-warning/10 border border-warning/30 rounded-lg hover:bg-warning/20 transition-fast flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
                Compare
              </Link>
            )}
          </div>
          
          {activity.is_breakthrough && (
            <span className="inline-flex items-center gap-1 px-3 py-1 text-sm font-semibold text-warning-foreground bg-warning/90 rounded-full">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Breakthrough
            </span>
          )}
        </div>

        {/* Stats Grid - Row 1: Ride Basics */}
        <div className="mb-3">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Ride Basics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <StatTile label="Distance" value={formatDistance(activity.total_distance_m, unitSystem)} />
            <StatTile label="Moving Time" value={formatTime(activity.moving_time_s)} />
            <StatTile label="Elevation" value={formatElevation(activity.elevation_gain_m, unitSystem)} />
            <StatTile label="Avg Speed" value={formatSpeed(activity.avg_speed_mps, unitSystem)} />
            <StatTile label="Avg HR" value={activity.avg_hr_bpm ? `${activity.avg_hr_bpm} bpm` : "—"} />
          </div>
        </div>

        {/* Stats Grid - Row 2: Training Metrics */}
        <div className="mb-6">
          <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Training Metrics</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatTile 
              label="Avg Power" 
              value={activity.avg_power_w ? `${activity.avg_power_w} W` : "—"} 
              subtitle={activity.power_source === "hr_derived" ? "HR-derived" : undefined}
            />
            <StatTile label="NP" value={activity.np_power_w ? `${activity.np_power_w} W` : "—"} />
            <StatTile label="IF" value={activity.intensity_factor ? activity.intensity_factor.toFixed(2) : "—"} />
            <StatTile label="TSS" value={activity.tss ? Math.round(activity.tss).toString() : "—"} />
            <StatTile 
              label="W'bal Min" 
              value={activity.wbal_min_pct != null ? `${Math.round(activity.wbal_min_pct)}%` : "—"} 
            />
            <StatTile label="Max HR" value={activity.max_hr_bpm ? `${activity.max_hr_bpm} bpm` : "—"} />
          </div>
        </div>

        {/* Peak Powers / Power Curve */}
        {activity.peaks && activity.peaks.length > 0 && (
          <ChartErrorBoundary chartName="Power Curve" height={250}>
            <ActivityPowerCurve peaks={activity.peaks} />
          </ChartErrorBoundary>
        )}

        {/* Zone Distribution Charts */}
        {(activity.power_zone_times || activity.hr_zone_times) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {activity.power_zone_times && (
              <ChartErrorBoundary chartName="Power Zones" height={200}>
                <ZoneChart 
                  title="Power Zones" 
                  zoneTimes={activity.power_zone_times} 
                  zoneColors={POWER_ZONE_COLORS}
                />
              </ChartErrorBoundary>
            )}
            {activity.hr_zone_times && (
              <ChartErrorBoundary chartName="HR Zones" height={200}>
                <ZoneChart 
                  title="HR Zones" 
                  zoneTimes={activity.hr_zone_times} 
                  zoneColors={HR_ZONE_COLORS}
                />
              </ChartErrorBoundary>
            )}
          </div>
        )}

        {/* Map */}
        {positions.length > 0 && (
          <div className="mb-6 sticky top-0 z-10">
            <ResizableMap
              positions={positions}
              hoveredPosition={hoveredPosition}
              height={mapHeight}
              onResizeStart={startResizeHeight}
              isResizing={isResizing}
              showResizeHandle={true}
            />
          </div>
        )}

        {/* Data Charts */}
        {CHARTS.map((chart) => {
          const { data, xKey, tickFormatter, ticks } = getChartData(chart);
          const hasData = data.some((d) => d[chart.dataKey as keyof typeof d] !== null);
          if (!hasData) return null;
          
          // Calculate Y-axis domain with margin
          const values = data
            .map((d) => d[chart.dataKey as keyof typeof d] as number | null)
            .filter((v): v is number => v !== null);
          const minVal = Math.min(...values);
          const maxVal = Math.max(...values);
          const range = maxVal - minVal;
          const margin = range * 0.1 || 5; // 10% margin, minimum 5
          const yMin = Math.max(0, Math.floor(minVal - margin));
          const yMax = Math.ceil(maxVal + margin);
          
          return (
            <ChartErrorBoundary key={chart.key} chartName={chart.label} height={200}>
              <ChartCard
                title={chart.label}
                action={
                  <button
                    onClick={() => toggleAxis(chart.key)}
                    className={`px-3 py-1 text-xs font-medium rounded-full transition-fast ${
                      axisModes[chart.key] === "distance"
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {axisModes[chart.key] === "distance" ? "Distance" : "Time"}
                  </button>
                }
                onExpand={() => setExpandedChart(chart.key)}
              >
              <ResponsiveContainer width="100%" height={200}>
                <LineChart 
                  data={data}
                  onMouseLeave={handleChartLeave}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey={xKey}
                    type="number"
                    domain={['dataMin', 'dataMax']}
                    tickFormatter={tickFormatter}
                    ticks={ticks}
                    interval={0}
                    tick={{ fontSize: 10, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                  />
                  <YAxis
                    domain={[yMin, yMax]}
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                    label={{ value: chart.unit, angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      // Update map marker when tooltip is active
                      if (active && payload?.[0]?.payload) {
                        const p = payload[0].payload;
                        const mode = axisModes[chart.key];
                        const pos = mode === "distance"
                          ? findPositionByDistance(p.distance_m)
                          : findPositionByElapsed(p.elapsed);
                        if (pos) {
                          setTimeout(() => setHoveredPosition(pos), 0);
                        }
                      }
                      // Render default-style tooltip
                      if (!active || !payload?.length) return null;
                      const value = payload[0].value;
                      return (
                        <div style={{
                          backgroundColor: "white",
                          border: "1px solid #e5e7eb",
                          borderRadius: "8px",
                          padding: "8px 12px",
                          fontSize: "12px",
                        }}>
                          {chart.label}: {typeof value === "number" ? value.toFixed(2) : value}
                        </div>
                      );
                    }}
                  />
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
              </ChartCard>
            </ChartErrorBoundary>
          );
        })}

        {/* W'bal Chart */}
        {wbalData && wbalData.wbal_series.length > 0 && (
          <ChartErrorBoundary chartName="W'bal" height={200}>
            <WbalChart 
              wbalData={wbalData} 
              findPositionByElapsed={findPositionByElapsed}
              setHoveredPosition={setHoveredPosition}
            />
          </ChartErrorBoundary>
        )}
      </div>

      {/* Chart expansion modal */}
      {expandedChart && (() => {
        const chart = CHARTS.find((c) => c.key === expandedChart);
        if (!chart) return null;
        
        // Prepare chart data with elapsed times
        const resampled = resampleByDistance(records);
        const chartData = resampled.map((r, i) => {
          const elapsed = i < timestamps.length ? timestamps[i] - firstTs : i * 10;
          return {
            ...r,
            elapsed,
          };
        });
        
        return (
          <ChartExpandModal
            chart={chart}
            data={chartData}
            axisMode={axisModes[chart.key]}
            onToggleAxis={() => toggleAxis(chart.key)}
            onClose={() => setExpandedChart(null)}
            formatDistance={(m) => formatDistance(m, unitSystem)}
            formatTime={(s) => formatTime(s)}
            ftpWatts={ftpWatts}
            lthrBpm={lthrBpm}
          />
        );
      })()}
    </div>
  );
}

function StatTile({ label, value, subtitle }: { label: string; value: string; subtitle?: string }) {
  return (
    <div className="bg-card rounded-lg border border-border p-3 text-center">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className="text-lg font-semibold text-foreground tabular-nums">
        {value}
      </div>
      {subtitle && (
        <div className="text-xs text-primary mt-0.5">
          {subtitle}
        </div>
      )}
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  action,
  onExpand,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  onExpand?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-6 bg-card rounded-lg border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {onExpand && (
            <button
              onClick={onExpand}
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-fast"
              aria-label="Expand chart"
              title="Expand chart"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            </button>
          )}
        </div>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}



function ZoneChart({ 
  title, 
  zoneTimes, 
  zoneColors 
}: { 
  title: string; 
  zoneTimes: Record<string, number>; 
  zoneColors: Record<string, string>;
}) {
  // Convert zone times to array and calculate percentages
  const zones = Object.entries(zoneTimes)
    .map(([zone, seconds]) => ({
      zone,
      seconds,
      label: `Z${zone}`,
    }))
    .sort((a, b) => parseInt(a.zone) - parseInt(b.zone));

  const totalSeconds = zones.reduce((sum, z) => sum + z.seconds, 0);
  
  if (totalSeconds === 0) return null;

  const formatZoneTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="bg-card rounded-lg border border-border p-4">
      <h3 className="text-sm font-semibold text-foreground mb-4">{title}</h3>
      <div className="space-y-2">
        {zones.map(({ zone, seconds, label }) => {
          const percentage = (seconds / totalSeconds) * 100;
          const color = zoneColors[zone] || "#6b7280";
          
          return (
            <div key={zone} className="flex items-center gap-3">
              <div className="w-8 text-xs font-medium text-muted-foreground">
                {label}
              </div>
              <div className="flex-1 h-6 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ 
                    width: `${Math.max(percentage, 1)}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <div className="w-16 text-xs text-right text-muted-foreground tabular-nums">
                {formatZoneTime(seconds)}
              </div>
              <div className="w-12 text-xs text-right text-muted-foreground/70 tabular-nums">
                {percentage.toFixed(0)}%
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-border flex justify-between text-xs text-muted-foreground">
        <span>Total</span>
        <span className="tabular-nums">{formatZoneTime(totalSeconds)}</span>
      </div>
    </div>
  );
}



function WbalChart({ 
  wbalData, 
  findPositionByElapsed,
  setHoveredPosition,
}: { 
  wbalData: WbalResponse;
  findPositionByElapsed: (elapsed: number) => [number, number] | null;
  setHoveredPosition: (pos: [number, number] | null) => void;
}) {
  const { wbal_series, w_prime_joules, wbal_min_pct } = wbalData;
  
  if (!w_prime_joules || wbal_series.length === 0) return null;

  // Find minimum point
  const minPoint = wbal_series.reduce((min: WbalPoint, point: WbalPoint) => 
    point.wbal_pct < min.wbal_pct ? point : min
  , wbal_series[0]);

  // Color function for W'bal level
  const getWbalColor = (pct: number): string => {
    if (pct > 50) return "#22c55e"; // Green
    if (pct > 25) return "#eab308"; // Yellow
    return "#ef4444"; // Red
  };

  const formatElapsedTime = (seconds: number): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Generate nice time ticks
  const maxTime = Math.max(...wbal_series.map(d => d.elapsed_s));
  const niceIntervals = [30, 60, 120, 180, 300, 600, 900, 1200, 1800, 3600];
  const idealInterval = maxTime / 10;
  const interval = niceIntervals.find(i => i >= idealInterval) || niceIntervals[niceIntervals.length - 1];
  const ticks: number[] = [];
  for (let t = 0; t <= maxTime; t += interval) {
    ticks.push(t);
  }

  return (
    <ChartCard 
      title="W'bal" 
      subtitle={`W' = ${Math.round(w_prime_joules / 1000)} kJ • Min: ${wbal_min_pct?.toFixed(0) ?? "—"}%`}
    >
      <ResponsiveContainer width="100%" height={200}>
        <LineChart 
          data={wbal_series}
          onMouseLeave={() => setHoveredPosition(null)}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          
          {/* Color bands for depletion zones */}
          <ReferenceArea y1={0} y2={25} fill="#fee2e2" fillOpacity={0.5} />
          <ReferenceArea y1={25} y2={50} fill="#fef9c3" fillOpacity={0.5} />
          <ReferenceArea y1={50} y2={100} fill="#dcfce7" fillOpacity={0.5} />
          
          <XAxis
            dataKey="elapsed_s"
            type="number"
            domain={['dataMin', 'dataMax']}
            tickFormatter={formatElapsedTime}
            ticks={ticks}
            interval={0}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickLine={{ stroke: "#d1d5db" }}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12, fill: "#6b7280" }}
            axisLine={{ stroke: "#d1d5db" }}
            tickLine={{ stroke: "#d1d5db" }}
            label={{ value: "%", angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload?.[0]?.payload) {
                const p = payload[0].payload;
                const pos = findPositionByElapsed(p.elapsed_s);
                if (pos) {
                  setTimeout(() => setHoveredPosition(pos), 0);
                }
              }
              if (!active || !payload?.length) return null;
              const point = payload[0].payload;
              return (
                <div style={{
                  backgroundColor: "white",
                  border: "1px solid #e5e7eb",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "12px",
                }}>
                  <div>W'bal: {point.wbal_pct.toFixed(0)}%</div>
                  <div style={{ color: "#6b7280" }}>
                    {(point.wbal_joules / 1000).toFixed(1)} kJ
                  </div>
                </div>
              );
            }}
          />
          
          {/* Threshold lines */}
          <ReferenceLine y={50} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.5} />
          <ReferenceLine y={25} stroke="#ef4444" strokeDasharray="3 3" strokeOpacity={0.5} />
          
          <Line
            type="monotone"
            dataKey="wbal_pct"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            name="W'bal"
          />
          
          {/* Minimum point marker */}
          <ReferenceDot
            x={minPoint.elapsed_s}
            y={minPoint.wbal_pct}
            r={6}
            fill={getWbalColor(minPoint.wbal_pct)}
            stroke="#fff"
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

