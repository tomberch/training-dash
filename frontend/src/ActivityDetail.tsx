import * as React from "react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceDot,
  ReferenceArea,
} from "recharts";
import type { WbalResponse, WbalPoint } from "./api";
import { formatDistance, formatTime, formatElevation, formatSpeed, formatActivityDate, formatActivityTime, formatElapsedTime, formatDistanceAxis, activityEndTimeIso } from "./format";
import type { UnitSystem } from "./format";
import { resampleByDistance } from "./resampler";
import { ErrorDisplay } from "./ErrorDisplay";
import { ResizableMap } from "./components/ResizableMap";
import { useResizableMap } from "./hooks/useResizableMap";
import { useActivitySummary } from "./hooks/useActivitySummary";
import { useActivityRecords } from "./hooks/useActivityRecords";
import { useActivityWbal } from "./hooks/useActivityWbal";
import { useActivitySameRoute } from "./hooks/useActivitySameRoute";
import { useActivityThresholds } from "./hooks/useActivityThresholds";
import { useLazySection } from "./hooks/useLazySection";
import { ChartExpandModal } from "./components/ChartExpandModal";
import { ActivityPowerCurve } from "./components/ActivityPowerCurve";
import { ChartErrorBoundary } from "./components/ErrorBoundary";
import { POWER_ZONE_COLORS, HR_ZONE_COLORS } from "./constants";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { deleteActivity, fetchMyXertCredentials, fetchMyGarminCredentials } from "./api";
import { ActivityActions } from "@/components/ActivityActions";
import { UploadToProviderDialog } from "@/components/UploadToProviderDialog";

function ActivityDetailLoadingSkeleton(): React.JSX.Element {
  return (
    <div className="p-6">
      <div className="space-y-6">
        {/* Back link */}
        <Skeleton className="h-5 w-32" />
        
        {/* Title row with badge and edit icon */}
        <div className="flex items-start gap-2">
          <Skeleton className="h-8 w-96" />
          <Skeleton className="h-5 w-5 mt-1.5 rounded" />
        </div>
        
        {/* Subtitle row with date and action buttons */}
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-64" />
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24 rounded-lg" />
            <Skeleton className="h-9 w-20 rounded-lg" />
          </div>
        </div>
        
        {/* Map */}
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="h-64 bg-muted flex items-center justify-center">
            <svg className="w-12 h-12 text-muted-foreground/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
          </div>
          {/* Resize handle placeholder */}
          <div className="h-3 bg-muted/80 flex items-center justify-center">
            <Skeleton className="w-20 h-1 rounded-full" />
          </div>
        </div>
        
        {/* Grouped metric cards skeleton */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="bg-card rounded-xl border border-border p-5">
              <div className="flex items-center gap-2 mb-4">
                <Skeleton className="w-5 h-5 rounded" />
                <Skeleton className="h-3 w-24" />
              </div>
              <div className="space-y-3">
                {[1, 2].map((j) => (
                  <div key={j} className="flex justify-between items-baseline">
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-5 w-20" />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        
        {/* Performance section */}
        <div>
          <Skeleton className="h-6 w-32 mb-2" />
          <Skeleton className="h-4 w-64 mb-4" />
        </div>
        
        {/* Chart */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center justify-between mb-3">
            <Skeleton className="h-5 w-20" />
            <Skeleton className="h-8 w-16 rounded" />
          </div>
          <div className="h-48 bg-muted rounded flex items-end justify-around p-4 gap-1">
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
  // Use focused hooks for activity data management
  const {
    loading: summaryLoading,
    error: summaryError,
    setError,
    activity,
    isEditingTitle,
    setIsEditingTitle,
    editedTitle,
    setEditedTitle,
    saveTitle,
    isGeneratingTitle,
    generateTitle,
  } = useActivitySummary(activityId);

  const {
    loading: recordsLoading,
    error: recordsError,
    geojson,
    records,
    timestamps,
    firstTs,
    positions,
    axisModes,
    toggleAxis,
    hoveredPosition,
    setHoveredPosition,
    findPositionByElapsed,
    findPositionByDistance,
    expandedChart,
    setExpandedChart,
  } = useActivityRecords(activityId);

  // Lazy-loaded data
  const { wbalData } = useActivityWbal(activityId);
  const { sameRoute } = useActivitySameRoute(activityId);
  const { ftpWatts, lthrBpm } = useActivityThresholds(activity, wbalData);

  // Delete state
  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  // Upload to provider state
  const [showUploadDialog, setShowUploadDialog] = React.useState(false);
  const [hasConnectedProviders, setHasConnectedProviders] = React.useState(false);

  // Check for connected providers on mount
  React.useEffect(() => {
    async function checkProviders() {
      try {
        const [xertStatus, garminStatus] = await Promise.all([
          fetchMyXertCredentials().catch(() => ({ configured: false })),
          fetchMyGarminCredentials().catch(() => ({ configured: false })),
        ]);
        setHasConnectedProviders(xertStatus.configured || garminStatus.configured);
      } catch {
        setHasConnectedProviders(false);
      }
    }
    checkProviders();
  }, []);

  async function handleDelete(): Promise<void> {
    setIsDeleting(true);
    try {
      await deleteActivity(activityId);
      toast.success("Activity deleted");
      onBack();
    } catch {
      toast.error("Failed to delete activity");
      setShowDeleteDialog(false);
    } finally {
      setIsDeleting(false);
    }
  }

  function handleUploadToProvider(): void {
    setShowUploadDialog(true);
  }

  function handleExportFit(): void {
    // Trigger file download via the API endpoint
    const url = `/api/activities/${activityId}/fit`;
    const link = document.createElement("a");
    link.href = url;
    link.download = `${activityId}.fit`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("FIT file download started");
  }

  // Lazy section loading
  const { sentinelRef: analysisSentinelRef, hasEntered: analysisVisible } = useLazySection();

  // Compute elevation loss and max grade from records
  // Max grade uses smoothed altitude data over 200m segments to reduce GPS noise
  const elevationStats = useMemo(() => {
    if (records.length < 2) {
      return { elevationLoss: 0, maxGradePct: null as number | null };
    }

    // First, smooth the altitude data with a moving average (11-point window ~= 40m at typical recording intervals)
    const smoothedAltitudes: (number | null)[] = [];
    const smoothWindow = 11;
    
    for (let i = 0; i < records.length; i++) {
      if (records[i].altitude_m == null) {
        smoothedAltitudes.push(null);
        continue;
      }
      
      let sum = 0;
      let count = 0;
      const halfWindow = Math.floor(smoothWindow / 2);
      for (let j = Math.max(0, i - halfWindow); j <= Math.min(records.length - 1, i + halfWindow); j++) {
        if (records[j].altitude_m != null) {
          sum += records[j].altitude_m!;
          count++;
        }
      }
      smoothedAltitudes.push(count > 0 ? sum / count : null);
    }

    let elevationLoss = 0;
    let maxGradePct: number | null = null;

    // Calculate elevation loss using smoothed data
    for (let i = 1; i < records.length; i++) {
      const prevAlt = smoothedAltitudes[i - 1];
      const currAlt = smoothedAltitudes[i];
      if (prevAlt != null && currAlt != null) {
        const altDiff = currAlt - prevAlt;
        if (altDiff < 0) {
          elevationLoss += Math.abs(altDiff);
        }
      }
    }

    // Calculate max grade over 200m segments using smoothed altitudes
    // This gives a more meaningful "steepest climb" value
    const segmentLength = 200; // meters - longer segment for more stable reading
    const minSegment = 150; // minimum segment to consider
    
    for (let i = 0; i < records.length; i++) {
      const start = records[i];
      const startAlt = smoothedAltitudes[i];
      if (startAlt == null || start.distance_m == null) continue;
      
      // Find end point approximately segmentLength meters ahead
      for (let j = i + 1; j < records.length; j++) {
        const end = records[j];
        const endAlt = smoothedAltitudes[j];
        if (endAlt == null || end.distance_m == null) continue;
        
        const distDiff = end.distance_m - start.distance_m;
        
        // Skip if we haven't reached minimum segment length
        if (distDiff < minSegment) continue;
        
        // Stop if we've exceeded target segment size
        if (distDiff > segmentLength) break;
        
        const altDiff = endAlt - startAlt;
        const grade = (altDiff / distDiff) * 100;
        
        // Only consider positive grades (uphill)
        if (grade > 0 && (maxGradePct === null || grade > maxGradePct)) {
          maxGradePct = grade;
        }
      }
    }

    return { 
      elevationLoss: Math.round(elevationLoss), 
      maxGradePct: maxGradePct !== null ? Math.round(maxGradePct * 10) / 10 : null 
    };
  }, [records]);

  // Build power-colored segments for map visualization
  // Uses 7-zone power model based on FTP
  const coloredSegments = useMemo(() => {
    if (!geojson || !ftpWatts || positions.length < 2) {
      return [];
    }

    // Power zone boundaries as % of FTP (standard 7-zone model)
    const zoneBoundaries = [
      { max: 0.55, zone: "1" },  // Recovery: <55%
      { max: 0.75, zone: "2" },  // Endurance: 55-75%
      { max: 0.90, zone: "3" },  // Tempo: 75-90%
      { max: 1.05, zone: "4" },  // Threshold: 90-105%
      { max: 1.20, zone: "5" },  // VO2max: 105-120%
      { max: 1.50, zone: "6" },  // Anaerobic: 120-150%
      { max: Infinity, zone: "7" },  // Neuromuscular: >150%
    ];

    const getPowerZone = (power: number): string => {
      const pctFtp = power / ftpWatts;
      for (const b of zoneBoundaries) {
        if (pctFtp <= b.max) return b.zone;
      }
      return "7";
    };

    const features = geojson.features.filter(
      (f) => f.geometry !== null && f.geometry.coordinates.length >= 2
    );

    if (features.length < 2) return [];

    const segments: { positions: [number, number][]; color: string }[] = [];
    let currentZone: string | null = null;
    let currentPositions: [number, number][] = [];

    for (const f of features) {
      const power = f.properties.power_w;
      const pos: [number, number] = [
        f.geometry!.coordinates[1],
        f.geometry!.coordinates[0],
      ];

      // Skip points without power data - use default color
      if (power == null) {
        if (currentPositions.length >= 2 && currentZone) {
          segments.push({
            positions: [...currentPositions],
            color: POWER_ZONE_COLORS[currentZone] || "#6366f1",
          });
        }
        currentZone = null;
        currentPositions = [pos];
        continue;
      }

      const zone = getPowerZone(power);

      if (zone !== currentZone) {
        // Save previous segment
        if (currentPositions.length >= 2 && currentZone) {
          segments.push({
            positions: [...currentPositions],
            color: POWER_ZONE_COLORS[currentZone] || "#6366f1",
          });
        }
        // Start new segment (include last point for continuity)
        currentZone = zone;
        currentPositions = currentPositions.length > 0 
          ? [currentPositions[currentPositions.length - 1], pos]
          : [pos];
      } else {
        currentPositions.push(pos);
      }
    }

    // Don't forget the last segment
    if (currentPositions.length >= 2 && currentZone) {
      segments.push({
        positions: currentPositions,
        color: POWER_ZONE_COLORS[currentZone] || "#6366f1",
      });
    }

    return segments;
  }, [geojson, ftpWatts, positions]);

  // Combined loading/error state
  const loading = summaryLoading || recordsLoading;
  const error = summaryError || recordsError;

  // Responsive layout hooks for resizable map
  const {
    height: mapHeight,
    isResizing,
    startResizeHeight,
  } = useResizableMap({
    storageKey: "activity-detail",
    defaultHeight: 250,
    minHeight: 150,
    maxHeight: 600,
    defaultWidthPercent: 40,
    minWidthPercent: 25,
    maxWidthPercent: 60,
  });

  const handleChartLeave = () => {
    setHoveredPosition(null);
  };

  if (error) {
    return (
      <div className="p-6">
        <ErrorDisplay error={error} context="loading activity" />
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
    <div className="p-8">
        {/* Header */}
        <div className="mb-8">
          {/* Back link */}
          <button 
            onClick={onBack}
            className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 mb-4 hover:underline"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to activities
          </button>
          
          {/* Title row */}
          {isEditingTitle ? (
            <div className="flex items-center gap-2 mb-2">
              <input
                type="text"
                value={editedTitle}
                onChange={(e) => setEditedTitle(e.target.value)}
                className="flex-1 max-w-2xl px-3 py-2 text-page-title bg-input border border-input-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
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
            <div className="flex items-start gap-2">
              <h1 className="text-page-title">
                {activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </h1>
              <button
                onClick={() => {
                  setEditedTitle(activity.title || "");
                  setIsEditingTitle(true);
                }}
                className="p-1.5 text-muted-foreground hover:text-primary transition mt-1"
                title="Edit title"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              {activity.title_source === "pending" && (
                <button
                  onClick={() => {
                    generateTitle().catch((err) => setError(err));
                  }}
                  disabled={isGeneratingTitle}
                  className="p-1.5 text-primary hover:text-primary/80 disabled:opacity-50 mt-1"
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
              {activity.is_breakthrough && (
                <span className="bg-warning/20 text-warning border border-warning/30 px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 mt-1.5">
                  <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  Breakthrough
                </span>
              )}
            </div>
          )}
          
          {/* Subtitle row with date and action buttons */}
          <div className="text-body-secondary mt-2 flex flex-wrap items-center justify-between gap-3">
            <span>
              {formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}
              {" · "}
              {formatActivityTime(activity.started_at, activity.utc_offset_minutes)}
              {" - "}
              {formatActivityTime(
                activityEndTimeIso(activity.started_at, activity.elapsed_time_s),
                activity.utc_offset_minutes,
              )}
            </span>
            
            {/* Action buttons and badge - right aligned */}
            <div className="flex items-center gap-2">
              <Link
                to={`/analyze?activity=${activityId}`}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-muted/50 hover:bg-muted text-foreground transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Analyze
              </Link>
              {sameRoute && sameRoute.route_id !== null && sameRoute.activities.length > 0 && (
                <Link
                  to={`/compare?base=${activityId}`}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-muted/50 hover:bg-muted text-foreground transition"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                  </svg>
                  Compare
                </Link>
              )}
              <ActivityActions
                onUploadToProvider={handleUploadToProvider}
                onExportFit={handleExportFit}
                hasConnectedProviders={hasConnectedProviders}
              />
              <button
                onClick={() => setShowDeleteDialog(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-destructive/10 hover:bg-destructive/20 text-destructive transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Delete
              </button>
            </div>
          </div>
        </div>

        {/* Map */}
        {positions.length > 0 && (
          <div className="mb-8 relative">
            <ResizableMap
              positions={positions}
              coloredSegments={coloredSegments.length > 0 ? coloredSegments : undefined}
              hoveredPosition={hoveredPosition}
              height={mapHeight}
              onResizeStart={startResizeHeight}
              isResizing={isResizing}
              showResizeHandle={true}
            />
            {/* Power zone legend - shown when colored segments are displayed */}
            {coloredSegments.length > 0 && (
              <div className="absolute bottom-6 left-12 z-[1000] bg-card/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-border shadow-lg">
                <div className="flex items-center gap-3 text-xs">
                  <span className="text-muted-foreground font-medium">Power</span>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["1"] }} />
                    <span className="text-foreground">Z1</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["2"] }} />
                    <span className="text-foreground">Z2</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["3"] }} />
                    <span className="text-foreground">Z3</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["4"] }} />
                    <span className="text-foreground">Z4</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["5"] }} />
                    <span className="text-foreground">Z5</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["6"] }} />
                    <span className="text-foreground">Z6</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS["7"] }} />
                    <span className="text-foreground">Z7</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Grouped Metric Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {/* Time & Distance Card */}
          <MetricGroupCard
            icon={
              <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            title="Time & Distance"
          >
            <MetricEntry label="Elapsed" value={formatTime(activity.elapsed_time_s)} />
            <MetricEntry label="Moving" value={formatTime(activity.moving_time_s)} />
            <MetricEntry 
              label="Distance" 
              value={formatDistance(activity.total_distance_m, unitSystem)} 
              prominent 
            />
          </MetricGroupCard>

          {/* Elevation Card */}
          <MetricGroupCard
            icon={
              <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
            }
            title="Elevation"
          >
            <MetricEntry 
              label="Gain" 
              value={formatElevation(activity.elevation_gain_m, unitSystem)} 
              valueClass="text-green-400"
            />
            <MetricEntry 
              label="Loss" 
              value={formatElevation(elevationStats.elevationLoss, unitSystem)} 
              valueClass="text-red-400"
            />
            <MetricEntry 
              label="Max Grade" 
              value={elevationStats.maxGradePct !== null ? `${elevationStats.maxGradePct}%` : "—"} 
            />
          </MetricGroupCard>

          {/* Speed Card */}
          <MetricGroupCard
            icon={
              <svg className="w-5 h-5 text-cyan-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            }
            title="Speed"
          >
            <MetricEntry 
              label="Average" 
              value={formatSpeed(activity.avg_speed_mps, unitSystem)} 
            />
            <MetricEntry 
              label="Max" 
              value={activity.max_speed_mps ? formatSpeed(activity.max_speed_mps, unitSystem) : "—"} 
            />
          </MetricGroupCard>

          {/* Heart Rate Card */}
          <MetricGroupCard
            icon={
              <svg className="w-5 h-5 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
              </svg>
            }
            title="Heart Rate"
          >
            <MetricEntry 
              label="Average" 
              value={activity.avg_hr_bpm ? `${activity.avg_hr_bpm} bpm` : "—"} 
            />
            <MetricEntry 
              label="Max" 
              value={activity.max_hr_bpm ? `${activity.max_hr_bpm} bpm` : "—"} 
            />
          </MetricGroupCard>

          {/* Power Card */}
          <MetricGroupCard
            icon={
              <svg className="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            }
            title="Power"
          >
            <MetricEntry 
              label="Average" 
              value={activity.avg_power_w ? `${activity.avg_power_w} W` : "—"} 
              subtitle={activity.power_source === "hr_derived" ? "HR-derived" : undefined}
            />
            <MetricEntry 
              label="Normalized" 
              value={activity.np_power_w ? `${activity.np_power_w} W` : "—"} 
            />
          </MetricGroupCard>

          {/* Training Load Card */}
          <MetricGroupCard
            icon={
              <svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            }
            title="Training Load"
          >
            <MetricEntry 
              label="TSS" 
              value={activity.tss ? Math.round(activity.tss).toString() : "—"} 
              tooltip={!ftpWatts && !activity.tss ? "Set FTP in Settings to calculate" : undefined}
            />
            <MetricEntry 
              label="IF" 
              value={activity.intensity_factor ? activity.intensity_factor.toFixed(2) : "—"} 
              tooltip={!ftpWatts && !activity.intensity_factor ? "Set FTP in Settings to calculate" : undefined}
            />
            <MetricEntry 
              label="W'bal Min" 
              value={activity.wbal_min_pct != null ? `${Math.round(activity.wbal_min_pct)}%` : "—"} 
            />
            {!ftpWatts && (
              <div className="pt-3 border-t border-border">
                <p className="text-caption">
                  Set FTP in Athlete profile to calculate training load metrics
                </p>
              </div>
            )}
          </MetricGroupCard>
        </div>

        {/* ========== PERFORMANCE SECTION ========== */}
        <section className="mb-8">
          <SectionHeader 
            title="Performance" 
            subtitle="Time series data and zone distribution"
          />

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
                    <RechartsTooltip
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

          {/* Zone Distribution Charts */}
          {(activity.power_zone_times || activity.hr_zone_times) && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
        </section>

        {/* ========== ANALYSIS SECTION ========== */}
        {/* Sentinel for lazy loading - placed before Analysis section */}
        <div ref={analysisSentinelRef} className="h-px" />
        
        {((activity.peaks && activity.peaks.length > 0) || (wbalData && wbalData.wbal_series.length > 0)) && (
          <section className="mb-8">
            <SectionHeader 
              title="Analysis" 
              subtitle="Power curve and W'bal depletion"
            />

            {analysisVisible ? (
              <>
                {/* Peak Powers / Power Curve */}
                {activity.peaks && activity.peaks.length > 0 && (
                  <ChartErrorBoundary chartName="Power Curve" height={250}>
                    <ActivityPowerCurve peaks={activity.peaks} />
                  </ChartErrorBoundary>
                )}

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
              </>
            ) : (
              /* Placeholder skeleton while waiting for intersection */
              <div className="space-y-6">
                <div className="bg-card rounded-lg border border-border p-4">
                  <Skeleton className="h-5 w-32 mb-4" />
                  <Skeleton className="h-[250px] w-full rounded" />
                </div>
                <div className="bg-card rounded-lg border border-border p-4">
                  <Skeleton className="h-5 w-24 mb-4" />
                  <Skeleton className="h-[200px] w-full rounded" />
                </div>
              </div>
            )}
          </section>
        )}

      {/* Delete confirmation dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete activity?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this activity and all its records.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Deleting…
                </span>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Upload to provider dialog */}
      <UploadToProviderDialog
        activityId={activityId}
        open={showUploadDialog}
        onOpenChange={setShowUploadDialog}
      />

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

function MetricGroupCard({ 
  icon, 
  title, 
  children 
}: { 
  icon: React.ReactNode; 
  title: string; 
  children: React.ReactNode;
}) {
  return (
    <div className="bg-card rounded-xl border border-border p-5 card-hover transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
      <div className="flex items-center gap-2 mb-4">
        {icon}
        <h3 className="font-semibold text-sm uppercase tracking-wider text-muted-foreground">{title}</h3>
      </div>
      <div className="space-y-3">
        {children}
      </div>
    </div>
  );
}

function MetricEntry({ 
  label, 
  value, 
  subtitle,
  tooltip,
  valueClass,
  prominent 
}: { 
  label: string; 
  value: string; 
  subtitle?: string;
  tooltip?: string;
  valueClass?: string;
  prominent?: boolean;
}) {
  const content = (
    <div className="flex justify-between items-baseline">
      <span className="text-muted-foreground text-sm">{label}</span>
      <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
        {value}
      </span>
    </div>
  );

  const withSubtitle = subtitle ? (
    <div className="flex justify-between items-baseline">
      <span className="text-muted-foreground text-sm">{label}</span>
      <div className="text-right">
        <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
          {value}
        </span>
        {subtitle && (
          <div className="text-xs text-primary">{subtitle}</div>
        )}
      </div>
    </div>
  ) : content;

  if (tooltip) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="cursor-help flex justify-between items-baseline">
            <span className="text-muted-foreground text-sm flex items-center gap-1">
              {label}
              <svg className="w-3 h-3 text-muted-foreground" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </span>
            <span className={`font-semibold ${prominent ? "text-xl" : "text-lg"} ${valueClass || "text-foreground"} tabular-nums`}>
              {value}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {tooltip}
        </TooltipContent>
      </Tooltip>
    );
  }

  return withSubtitle;
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }): React.JSX.Element {
  return (
    <div className="mb-4 pb-2 border-b border-border">
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {subtitle && (
        <p className="text-body-secondary mt-0.5">{subtitle}</p>
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
            <p className="text-caption">{subtitle}</p>
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
              <div className="w-32 text-xs font-medium text-muted-foreground shrink-0">
                {label}: {percentage.toFixed(0)}%{" "}
                <span className="text-muted-foreground/70">
                  ({formatZoneTime(seconds)})
                </span>
              </div>
              <div className="flex-1 h-5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-300"
                  style={{
                    width: `${Math.max(percentage, 1)}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-border flex justify-between text-caption">
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
          <RechartsTooltip
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

