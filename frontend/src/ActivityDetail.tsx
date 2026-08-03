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
  ReferenceDot,
  ReferenceArea,
} from "recharts";
import type { Activity, GeoJSONFeatureCollection, CompareResponse, SameRouteResponse, GapPoint, WbalResponse, ThresholdEntry } from "./api";
import { ApiError, fetchActivity, fetchActivityRecords, fetchActivityWbal, fetchSameRouteActivities, fetchComparison, updateActivityTitle, generateActivityTitle, fetchThresholds } from "./api";
import { formatDistance, formatTime, formatElevation, formatSpeed } from "./format";
import type { UnitSystem } from "./format";
import { resampleByDistance } from "./resampler";
import type { FitRecord } from "./resampler";
import { ErrorDisplay } from "./ErrorDisplay";
import { ResizableMap } from "./components/ResizableMap";
import { useResizableMap } from "./hooks/useResizableMap";
import { ChartExpandModal } from "./components/ChartExpandModal";
import { ActivityPowerCurve } from "./components/ActivityPowerCurve";
import { ChartErrorBoundary } from "./components/ErrorBoundary";

type AxisMode = "time" | "distance";

function gapColor(gap: number): string {
  if (gap < -0.5) return "#10b981"; // green = faster
  if (gap > 0.5) return "#ef4444"; // red = slower
  return "#6366f1"; // neutral indigo
}

function positionsByDistance(gpsFeatures: GeoJSONFeatureCollection["features"]): { distance_m: number; pos: [number, number] }[] {
  return gpsFeatures
    .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
    .map((f) => ({
      distance_m: f.properties.distance_m,
      pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
    }));
}

function buildColoredSegments(
  gapSeries: GapPoint[],
  posByDist: { distance_m: number; pos: [number, number] }[]
): { positions: [number, number][]; color: string }[] {
  if (gapSeries.length < 2 || posByDist.length < 2) return [];

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

// Zone colors (matching typical training zone colors)
const POWER_ZONE_COLORS: Record<string, string> = {
  "1": "#9ca3af", // Recovery - gray
  "2": "#3b82f6", // Endurance - blue
  "3": "#22c55e", // Tempo - green
  "4": "#eab308", // Threshold - yellow
  "5": "#f97316", // VO2max - orange
  "6": "#ef4444", // Anaerobic - red
  "7": "#7c3aed", // Neuromuscular - purple
};

const HR_ZONE_COLORS: Record<string, string> = {
  "1": "#9ca3af", // Recovery - gray
  "2": "#3b82f6", // Aerobic - blue
  "3": "#22c55e", // Tempo - green
  "4": "#eab308", // Threshold - yellow
  "5": "#ef4444", // VO2max - red
};

interface Props {
  activityId: number;
  onBack: () => void;
  unitSystem?: UnitSystem;
}

function geojsonToRecords(geojson: GeoJSONFeatureCollection): FitRecord[] {
  return geojson.features.map((f) => ({
    distance_m: f.properties.distance_m,
    hr_bpm: f.properties.hr_bpm,
    power_w: f.properties.power_w,
    speed_mps: f.properties.speed_mps,
    altitude_m: f.properties.altitude_m,
  }));
}

function geojsonToTimestamps(geojson: GeoJSONFeatureCollection): number[] {
  return geojson.features.map((f) => new Date(f.properties.timestamp).getTime() / 1000);
}

export function ActivityDetail({ activityId, onBack, unitSystem = "metric" }: Props) {
  const [activity, setActivity] = useState<Activity | null>(null);
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [axisModes, setAxisModes] = useState<{ [key: string]: AxisMode }>({
    speed: "time",
    hr: "time",
    power: "time",
    elevation: "time",
  });
  const [sameRoute, setSameRoute] = useState<SameRouteResponse | null>(null);
  const [compareOtherId, setCompareOtherId] = useState<number | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [wbalData, setWbalData] = useState<WbalResponse | null>(null);
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");
  const [isGeneratingTitle, setIsGeneratingTitle] = useState(false);
  const [expandedChart, setExpandedChart] = useState<string | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);

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

  useEffect(() => {
    setComparison(null);
    setCompareOtherId(null);
    setWbalData(null);
    Promise.all([
      fetchActivity(activityId),
      fetchActivityRecords(activityId),
      fetchSameRouteActivities(activityId),
      fetchActivityWbal(activityId),
      fetchThresholds(),
    ])
      .then(([a, g, sr, wbal, th]) => {
        setActivity(a);
        setGeojson(g);
        setSameRoute(sr);
        setWbalData(wbal);
        setThresholds(th);
      })
      .catch((e) => setError(e));
  }, [activityId]);

  useEffect(() => {
    if (compareOtherId === null) {
      setComparison(null);
      return;
    }
    fetchComparison(activityId, compareOtherId)
      .then(setComparison)
      .catch((e) => setError(e));
  }, [activityId, compareOtherId]);

  const records = useMemo(() => (geojson ? geojsonToRecords(geojson) : []), [geojson]);
  const timestamps = useMemo(() => (geojson ? geojsonToTimestamps(geojson) : []), [geojson]);
  const posByDist = useMemo(() => (geojson ? positionsByDistance(geojson.features) : []), [geojson]);
  const firstTs = useMemo(() => timestamps.length > 0 ? timestamps[0] : 0, [timestamps]);

  // Get applicable threshold for the activity date (most recent threshold before or on activity date)
  const applicableThreshold = useMemo(() => {
    if (!activity || thresholds.length === 0) return null;
    const activityDate = new Date(activity.started_at).toISOString().split("T")[0];
    // Thresholds are sorted by effective_date descending
    const applicable = thresholds.find((t) => t.effective_date <= activityDate);
    return applicable ?? thresholds[thresholds.length - 1]; // fallback to oldest if none applicable
  }, [activity, thresholds]);

  // Get FTP from wbalData (preferred) or threshold
  const ftpWatts = wbalData?.ftp_watts ?? applicableThreshold?.ftp_watts ?? null;
  const lthrBpm = applicableThreshold?.lthr_bpm ?? null;

  // Create a lookup for positions by elapsed time
  const posByElapsed = useMemo(() => {
    if (!geojson || timestamps.length === 0) return [];
    const first = timestamps[0];
    return geojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => ({
        elapsed: new Date(f.properties.timestamp).getTime() / 1000 - first,
        pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
      }));
  }, [geojson, timestamps]);

  // Find nearest position for a given elapsed time or distance
  const findPositionByElapsed = (elapsed: number): [number, number] | null => {
    if (posByElapsed.length === 0) return null;
    let closest = posByElapsed[0];
    let minDiff = Math.abs(closest.elapsed - elapsed);
    for (const p of posByElapsed) {
      const diff = Math.abs(p.elapsed - elapsed);
      if (diff < minDiff) {
        minDiff = diff;
        closest = p;
      }
    }
    return closest.pos;
  };

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

  const handleChartLeave = () => {
    setHoveredPosition(null);
  };

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
        <div className="max-w-6xl mx-auto">
          <ErrorDisplay error={error} context="loading activity" />
        </div>
      </div>
    );
  }

  if (!activity || !geojson) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  const gpsFeatures = geojson.features.filter(
    (f) => f.geometry !== null && f.geometry.coordinates.length >= 2
  );
  const positions: [number, number][] = gpsFeatures.map((f) => [
    f.geometry!.coordinates[1],
    f.geometry!.coordinates[0],
  ]);

  function toggleAxis(chartKey: string) {
    setAxisModes((prev) => ({
      ...prev,
      [chartKey]: prev[chartKey] === "time" ? "distance" : "time",
    }));
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

  const otherPositions: [number, number][] | null = comparison?.other_geojson
    ? comparison.other_geojson.features
        .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
        .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]])
    : null;

  const gapSeries = comparison?.gap_series ?? [];
  const coloredSegments = comparison?.comparable
    ? buildColoredSegments(gapSeries, posByDist)
    : [];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button
            onClick={onBack}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            &larr; Back
          </button>
          <div className="flex-1">
            {isEditingTitle ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="flex-1 px-3 py-2 text-lg font-bold text-gray-900 dark:text-white bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      updateActivityTitle(activityId, editedTitle)
                        .then((updated) => {
                          setActivity({ ...activity!, title: updated.title, title_source: updated.title_source });
                          setIsEditingTitle(false);
                        })
                        .catch((e) => setError(e));
                    } else if (e.key === "Escape") {
                      setIsEditingTitle(false);
                    }
                  }}
                />
                <button
                  onClick={() => {
                    updateActivityTitle(activityId, editedTitle)
                      .then((updated) => {
                        setActivity({ ...activity!, title: updated.title, title_source: updated.title_source });
                        setIsEditingTitle(false);
                      })
                      .catch((e) => setError(e));
                  }}
                  className="px-3 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
                >
                  Save
                </button>
                <button
                  onClick={() => setIsEditingTitle(false)}
                  className="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    {activity.title || new Date(activity.started_at).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                  </h1>
                  {activity.title_source === "pending" && (
                    <button
                      onClick={() => {
                        setIsGeneratingTitle(true);
                        generateActivityTitle(activityId)
                          .then((updated) => {
                            setActivity({ ...activity!, title: updated.title, title_source: updated.title_source });
                          })
                          .catch((e) => setError(e))
                          .finally(() => setIsGeneratingTitle(false));
                      }}
                      disabled={isGeneratingTitle}
                      className="p-1 text-indigo-500 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 disabled:opacity-50"
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
                    className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                    title="Edit title"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                </div>
                {/* Date/time subtitle */}
                <div className="flex items-center gap-4 text-base text-gray-500 dark:text-gray-400 mt-1">
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
                    <span className="text-gray-400 dark:text-gray-500">({formatTime(activity.elapsed_time_s)})</span>
                  </span>
                </div>
              </>
            )}
          </div>
          {activity.is_breakthrough && (
            <span className="inline-flex items-center gap-1 px-3 py-1 text-sm font-semibold text-amber-800 bg-amber-100 dark:text-amber-200 dark:bg-amber-900/50 rounded-full">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
              Breakthrough
            </span>
          )}
        </div>

        {/* Stats Grid - Row 1: Ride Basics */}
        <div className="mb-3">
          <h2 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Ride Basics</h2>
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
          <h2 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Training Metrics</h2>
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

        {/* Compare selector */}
        {sameRoute && sameRoute.route_id !== null && sameRoute.activities.length > 0 && (
          <div className="mb-6 p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Compare with another ride on this route
            </label>
            <select
              value={compareOtherId ?? ""}
              onChange={(e) => setCompareOtherId(e.target.value ? Number(e.target.value) : null)}
              className="w-full sm:w-auto px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">Select a ride...</option>
              {sameRoute.activities.map((a) => (
                <option key={a.id} value={a.id}>
                  {new Date(a.started_at).toLocaleDateString()} — {formatDistance(a.total_distance_m, unitSystem)}
                </option>
              ))}
            </select>
          </div>
        )}

        {comparison && !comparison.comparable && (
          <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg text-yellow-700 dark:text-yellow-400">
            These rides are not on the same route and cannot be compared.
          </div>
        )}

        {/* Map */}
        {positions.length > 0 && (
          <div className="mb-6 sticky top-0 z-10">
            <ResizableMap
              positions={positions}
              coloredSegments={coloredSegments}
              otherPositions={otherPositions}
              hoveredPosition={hoveredPosition}
              height={mapHeight}
              onResizeStart={startResizeHeight}
              isResizing={isResizing}
              showResizeHandle={true}
            />
          </div>
        )}

        {/* Gap Chart (comparison mode) */}
        {comparison && comparison.comparable && gapSeries.length > 0 && (
          <ChartErrorBoundary chartName="Time Gap" height={200}>
            <ChartCard title="Time Gap" subtitle="vs comparison ride">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={gapSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="distance_m"
                    tickFormatter={(v) => formatDistance(v, unitSystem)}
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: "#6b7280" }}
                    axisLine={{ stroke: "#d1d5db" }}
                    tickLine={{ stroke: "#d1d5db" }}
                    label={{ value: "Gap (s)", angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "white",
                      border: "1px solid #e5e7eb",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="gap_s"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={false}
                    name="Time Gap"
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          </ChartErrorBoundary>
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
                    className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                      axisModes[chart.key] === "distance"
                        ? "bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
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
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
        {label}
      </div>
      <div className="text-lg font-semibold text-gray-900 dark:text-white tabular-nums">
        {value}
      </div>
      {subtitle && (
        <div className="text-xs text-indigo-500 dark:text-indigo-400 mt-0.5">
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
    <div className="mb-6 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
          {subtitle && (
            <p className="text-xs text-gray-500 dark:text-gray-400">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {action}
          {onExpand && (
            <button
              onClick={onExpand}
              className="p-1.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 rounded transition-colors"
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
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">{title}</h3>
      <div className="space-y-2">
        {zones.map(({ zone, seconds, label }) => {
          const percentage = (seconds / totalSeconds) * 100;
          const color = zoneColors[zone] || "#6b7280";
          
          return (
            <div key={zone} className="flex items-center gap-3">
              <div className="w-8 text-xs font-medium text-gray-600 dark:text-gray-400">
                {label}
              </div>
              <div className="flex-1 h-6 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{ 
                    width: `${Math.max(percentage, 1)}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <div className="w-16 text-xs text-right text-gray-600 dark:text-gray-400 tabular-nums">
                {formatZoneTime(seconds)}
              </div>
              <div className="w-12 text-xs text-right text-gray-500 dark:text-gray-500 tabular-nums">
                {percentage.toFixed(0)}%
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700 flex justify-between text-xs text-gray-500 dark:text-gray-400">
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
  const minPoint = wbal_series.reduce((min, point) => 
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

