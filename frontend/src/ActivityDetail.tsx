import * as React from "react";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, ResponsiveContainer,
} from "recharts";
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
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { deleteActivity, fetchMyXertCredentials, fetchMyGarminCredentials, updateActivityType, updateActivityBike, ACTIVITY_TYPES, ACTIVITY_TYPE_LABELS } from "./api";
import type { ActivityType, Bike } from "./api";
import { fetchBikes } from "./api/bikes";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { ActivityActions } from "@/components/ActivityActions";
import { UploadToProviderDialog } from "@/components/UploadToProviderDialog";
import { BikePicker } from "@/components/BikePicker";
import { getNiceTicks, getNiceTimeTicks } from "./lib/chartUtils";
import { notifyError } from "@/lib/notify";
import {
  ActivityDetailSkeleton, MetricGroupCard, MetricEntry,
  SectionHeader, ChartCard, ZoneChart, WbalChart,
} from "./components/activity";

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
  const {
    loading: summaryLoading, error: summaryError, setError, activity, setActivity,
    isEditingTitle, setIsEditingTitle, editedTitle, setEditedTitle,
    saveTitle, isGeneratingTitle, generateTitle,
  } = useActivitySummary(activityId);

  const {
    loading: recordsLoading, error: recordsError, geojson, records,
    timestamps, firstTs, positions, axisModes, toggleAxis,
    hoveredPosition, setHoveredPosition, findPositionByElapsed,
    findPositionByDistance, expandedChart, setExpandedChart,
  } = useActivityRecords(activityId);

  const { wbalData } = useActivityWbal(activityId);
  const { sameRoute } = useActivitySameRoute(activityId);
  const { ftpWatts, lthrBpm } = useActivityThresholds(activity, wbalData);

  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [showUploadDialog, setShowUploadDialog] = React.useState(false);
  const [hasConnectedProviders, setHasConnectedProviders] = React.useState(false);
  const [activityType, setActivityType] = React.useState<ActivityType | null>(null);
  const [isUpdatingType, setIsUpdatingType] = React.useState(false);
  const [defaultBike, setDefaultBike] = React.useState<Bike | null>(null);

  // Sync activity type state when activity loads
  React.useEffect(() => {
    if (activity) {
      setActivityType(activity.activity_type);
    }
  }, [activity]);

  // Fetch default bike for "assumed default" indicator
  React.useEffect(() => {
    async function loadDefaultBike() {
      try {
        const bikes = await fetchBikes(false);
        const def = bikes.find((b) => b.is_default);
        setDefaultBike(def || null);
      } catch {
        // Silently fail - not critical
      }
    }
    loadDefaultBike();
  }, []);

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

  async function handleActivityTypeChange(newType: ActivityType | null): Promise<void> {
    if (newType === activityType) return;
    setIsUpdatingType(true);
    try {
      await updateActivityType(activityId, newType);
      setActivityType(newType);
      toast.success(`Activity type ${newType ? `set to ${newType}` : "cleared"}`);
    } catch {
      notifyError("Failed to update activity type", { bellType: "activity_update_failed" });
    } finally {
      setIsUpdatingType(false);
    }
  }

  async function handleBikeChange(bikeId: number | null): Promise<void> {
    const updated = await updateActivityBike(activityId, bikeId);
    // Update local activity state with new bike
    if (activity) {
      setActivity({ ...activity, bike_id: updated.bike_id, bike: updated.bike });
      const bikeName = updated.bike?.name;
      toast.success(bikeName ? `Bike set to ${bikeName}` : "Bike removed");
    }
  }

  async function handleDelete(): Promise<void> {
    setIsDeleting(true);
    try {
      await deleteActivity(activityId);
      toast.success("Activity deleted");
      onBack();
    } catch {
      notifyError("Failed to delete activity", { bellType: "activity_delete_failed" });
      setShowDeleteDialog(false);
    } finally {
      setIsDeleting(false);
    }
  }

  function handleUploadToProvider(): void { setShowUploadDialog(true); }
  function handleExportFit(): void {
    const link = document.createElement("a");
    link.href = `/api/activities/${activityId}/fit`;
    link.download = `${activityId}.fit`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success("FIT file download started");
  }

  const { sentinelRef: analysisSentinelRef, hasEntered: analysisVisible } = useLazySection();



  const elevationStats = useMemo(() => {
    if (records.length < 2) return { elevationLoss: 0, maxGradePct: null as number | null };
    const smoothedAltitudes: (number | null)[] = [];
    const smoothWindow = 11;
    for (let i = 0; i < records.length; i++) {
      if (records[i].altitude_m == null) { smoothedAltitudes.push(null); continue; }
      let sum = 0, count = 0;
      const halfWindow = Math.floor(smoothWindow / 2);
      for (let j = Math.max(0, i - halfWindow); j <= Math.min(records.length - 1, i + halfWindow); j++) {
        if (records[j].altitude_m != null) { sum += records[j].altitude_m!; count++; }
      }
      smoothedAltitudes.push(count > 0 ? sum / count : null);
    }
    let elevationLoss = 0;
    let maxGradePct: number | null = null;
    for (let i = 1; i < records.length; i++) {
      const prevAlt = smoothedAltitudes[i - 1], currAlt = smoothedAltitudes[i];
      if (prevAlt != null && currAlt != null && currAlt - prevAlt < 0) elevationLoss += Math.abs(currAlt - prevAlt);
    }
    const segmentLength = 200, minSegment = 150;
    for (let i = 0; i < records.length; i++) {
      const start = records[i], startAlt = smoothedAltitudes[i];
      if (startAlt == null || start.distance_m == null) continue;
      for (let j = i + 1; j < records.length; j++) {
        const end = records[j], endAlt = smoothedAltitudes[j];
        if (endAlt == null || end.distance_m == null) continue;
        const distDiff = end.distance_m - start.distance_m;
        if (distDiff < minSegment) continue;
        if (distDiff > segmentLength) break;
        const grade = ((endAlt - startAlt) / distDiff) * 100;
        if (grade > 0 && (maxGradePct === null || grade > maxGradePct)) maxGradePct = grade;
      }
    }
    return { elevationLoss: Math.round(elevationLoss), maxGradePct: maxGradePct !== null ? Math.round(maxGradePct * 10) / 10 : null };
  }, [records]);



  const coloredSegments = useMemo(() => {
    if (!geojson || !ftpWatts || positions.length < 2) return [];
    const zoneBoundaries = [
      { max: 0.55, zone: "1" }, { max: 0.75, zone: "2" }, { max: 0.90, zone: "3" },
      { max: 1.05, zone: "4" }, { max: 1.20, zone: "5" }, { max: 1.50, zone: "6" }, { max: Infinity, zone: "7" },
    ];
    const getPowerZone = (power: number): string => {
      const pctFtp = power / ftpWatts;
      for (const b of zoneBoundaries) if (pctFtp <= b.max) return b.zone;
      return "7";
    };
    const features = geojson.features.filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2);
    if (features.length < 2) return [];
    const segments: { positions: [number, number][]; color: string }[] = [];
    let currentZone: string | null = null;
    let currentPositions: [number, number][] = [];
    for (const f of features) {
      const power = f.properties.power_w;
      const pos: [number, number] = [f.geometry!.coordinates[1], f.geometry!.coordinates[0]];
      if (power == null) {
        if (currentPositions.length >= 2 && currentZone) segments.push({ positions: [...currentPositions], color: POWER_ZONE_COLORS[currentZone] || "#6366f1" });
        currentZone = null; currentPositions = [pos]; continue;
      }
      const zone = getPowerZone(power);
      if (zone !== currentZone) {
        if (currentPositions.length >= 2 && currentZone) segments.push({ positions: [...currentPositions], color: POWER_ZONE_COLORS[currentZone] || "#6366f1" });
        currentZone = zone;
        currentPositions = currentPositions.length > 0 ? [currentPositions[currentPositions.length - 1], pos] : [pos];
      } else {
        currentPositions.push(pos);
      }
    }
    if (currentPositions.length >= 2 && currentZone) segments.push({ positions: currentPositions, color: POWER_ZONE_COLORS[currentZone] || "#6366f1" });
    return segments;
  }, [geojson, ftpWatts, positions]);



  const loading = summaryLoading || recordsLoading;
  const error = summaryError || recordsError;
  const { height: mapHeight, isResizing, startResizeHeight } = useResizableMap({
    storageKey: "activity-detail", defaultHeight: 250, minHeight: 150, maxHeight: 600,
    defaultWidthPercent: 40, minWidthPercent: 25, maxWidthPercent: 60,
  });
  const handleChartLeave = () => setHoveredPosition(null);

  if (error) return <div className="p-6"><ErrorDisplay error={error} context="loading activity" /></div>;
  if (loading || !activity || !geojson) return <ActivityDetailSkeleton />;

  interface ChartDataPoint {
    distance_m: number; elapsed: number; speed_mps: number | null;
    hr_bpm: number | null; power_w: number | null; altitude_m: number | null;
  }

  function getChartData(chart: ChartConfig) {
    const mode = axisModes[chart.key];
    if (mode === "distance") {
      const resampled = resampleByDistance(records);
      const data: ChartDataPoint[] = resampled.map((r, i) => ({
        distance_m: r.distance_m, elapsed: i, speed_mps: r.speed_mps,
        hr_bpm: r.hr_bpm, power_w: r.power_w, altitude_m: r.altitude_m,
      }));
      const maxDistance = Math.max(...data.map(d => d.distance_m));
      return { data, xKey: "distance_m" as const, xLabel: "Distance", tickFormatter: formatDistanceAxis, ticks: getNiceTicks(0, maxDistance, 10) };
    }
    const data: ChartDataPoint[] = timestamps.map((ts, i) => ({
      distance_m: records[i].distance_m, elapsed: ts - firstTs, speed_mps: records[i].speed_mps,
      hr_bpm: records[i].hr_bpm, power_w: records[i].power_w, altitude_m: records[i].altitude_m,
    }));
    const maxTime = Math.max(...data.map(d => d.elapsed));
    return { data, xKey: "elapsed" as const, xLabel: "Time", tickFormatter: formatElapsedTime, ticks: getNiceTimeTicks(maxTime, 10) };
  }



  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <button onClick={onBack} className="text-muted-foreground hover:text-foreground transition flex items-center gap-1 mb-4 hover:underline">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          Back to activities
        </button>
        {isEditingTitle ? (
          <div className="flex items-center gap-2 mb-2">
            <input type="text" value={editedTitle} onChange={(e) => setEditedTitle(e.target.value)}
              className="flex-1 max-w-2xl px-3 py-2 text-page-title bg-input border border-input-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ring" autoFocus
              onKeyDown={(e) => { if (e.key === "Enter") saveTitle(editedTitle).catch((err) => setError(err)); else if (e.key === "Escape") setIsEditingTitle(false); }} />
            <button onClick={() => saveTitle(editedTitle).catch((err) => setError(err))} className="px-3 py-2 text-sm font-medium text-primary-foreground bg-primary rounded-lg hover:bg-primary/80">Save</button>
            <button onClick={() => setIsEditingTitle(false)} className="px-3 py-2 text-sm font-medium text-foreground bg-card border border-border rounded-lg hover:bg-muted">Cancel</button>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <h1 className="text-page-title">{activity.title || formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</h1>
            <button onClick={() => { setEditedTitle(activity.title || ""); setIsEditingTitle(true); }} className="p-1.5 text-muted-foreground hover:text-primary transition mt-1" title="Edit title">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
            </button>
            {activity.title_source === "pending" && (
              <button onClick={() => generateTitle().catch((err) => setError(err))} disabled={isGeneratingTitle} className="p-1.5 text-primary hover:text-primary/80 disabled:opacity-50 mt-1" title="Generate location-based title from GPS">
                {isGeneratingTitle ? <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                  : <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" /></svg>}
              </button>
            )}
            {activity.is_breakthrough && (
              <span className="bg-warning/20 text-warning border border-warning/30 px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 mt-1.5">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" /></svg>Breakthrough
              </span>
            )}
          </div>
        )}


        <div className="text-body-secondary mt-2 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span>{formatActivityDate(activity.started_at, activity.utc_offset_minutes, { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}{" · "}{formatActivityTime(activity.started_at, activity.utc_offset_minutes)}{" - "}{formatActivityTime(activityEndTimeIso(activity.started_at, activity.elapsed_time_s), activity.utc_offset_minutes)}</span>
            <span className="text-border">·</span>
            <DropdownMenu>
              <DropdownMenuTrigger>
                <button
                  disabled={isUpdatingType}
                  className="flex items-center gap-1.5 px-2 py-1 text-sm rounded-md hover:bg-muted transition disabled:opacity-50"
                >
                  {isUpdatingType ? (
                    <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A2 2 0 013 12V7a4 4 0 014-4z" />
                    </svg>
                  )}
                  <span className="capitalize">{activityType ?? "Unclassified"}</span>
                  <svg className="w-3.5 h-3.5 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem onClick={() => handleActivityTypeChange(null)} className={activityType === null ? "bg-muted" : ""}>
                  Unclassified
                </DropdownMenuItem>
                {ACTIVITY_TYPES.map((type) => (
                  <DropdownMenuItem
                    key={type}
                    onClick={() => handleActivityTypeChange(type)}
                    className={activityType === type ? "bg-muted" : ""}
                  >
                    {ACTIVITY_TYPE_LABELS[type]}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <span className="text-border">·</span>
            <BikePicker
              selectedBike={activity.bike}
              defaultBike={defaultBike}
              onChange={handleBikeChange}
            />
          </div>
          <div className="flex items-center gap-2">
            <Link to={`/analyze?activity=${activityId}`} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-muted/50 hover:bg-muted text-foreground transition">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>Analyze
            </Link>
            {sameRoute && sameRoute.route_id !== null && sameRoute.activities.length > 0 && (
              <Link to={`/compare?base=${activityId}`} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-muted/50 hover:bg-muted text-foreground transition">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>Compare
              </Link>
            )}
            <ActivityActions onUploadToProvider={handleUploadToProvider} onExportFit={handleExportFit} hasConnectedProviders={hasConnectedProviders} />
            <button onClick={() => setShowDeleteDialog(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-destructive/10 hover:bg-destructive/20 text-destructive transition">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>Delete
            </button>
          </div>
        </div>
      </div>



      {/* Map */}
      {positions.length > 0 && (
        <div className="mb-8 relative">
          <ResizableMap positions={positions} coloredSegments={coloredSegments.length > 0 ? coloredSegments : undefined} hoveredPosition={hoveredPosition} height={mapHeight} onResizeStart={startResizeHeight} isResizing={isResizing} showResizeHandle={true} />
          {coloredSegments.length > 0 && (
            <div className="absolute bottom-6 left-12 z-[1000] bg-card/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-border shadow-lg">
              <div className="flex items-center gap-3 text-xs">
                <span className="text-muted-foreground font-medium">Power</span>
                {["1","2","3","4","5","6","7"].map(z => (
                  <div key={z} className="flex items-center gap-1.5"><span className="w-3 h-3 rounded-full" style={{ backgroundColor: POWER_ZONE_COLORS[z] }} /><span className="text-foreground">Z{z}</span></div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <MetricGroupCard icon={<svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>} title="Time & Distance">
          <MetricEntry label="Elapsed" value={formatTime(activity.elapsed_time_s)} />
          <MetricEntry label="Moving" value={formatTime(activity.moving_time_s)} />
          <MetricEntry label="Distance" value={formatDistance(activity.total_distance_m, unitSystem)} prominent />
        </MetricGroupCard>
        <MetricGroupCard icon={<svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" /></svg>} title="Elevation">
          <MetricEntry label="Gain" value={formatElevation(activity.elevation_gain_m, unitSystem)} valueClass="text-green-400" />
          <MetricEntry label="Loss" value={formatElevation(elevationStats.elevationLoss, unitSystem)} valueClass="text-red-400" />
          <MetricEntry label="Max Grade" value={elevationStats.maxGradePct !== null ? `${elevationStats.maxGradePct}%` : "—"} />
        </MetricGroupCard>
        <MetricGroupCard icon={<svg className="w-5 h-5 text-cyan-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>} title="Speed">
          <MetricEntry label="Average" value={formatSpeed(activity.avg_speed_mps, unitSystem)} />
          <MetricEntry label="Max" value={activity.max_speed_mps ? formatSpeed(activity.max_speed_mps, unitSystem) : "—"} />
        </MetricGroupCard>


        <MetricGroupCard icon={<svg className="w-5 h-5 text-pink-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" /></svg>} title="Heart Rate">
          <MetricEntry label="Average" value={activity.avg_hr_bpm ? `${activity.avg_hr_bpm} bpm` : "—"} />
          <MetricEntry label="Max" value={activity.max_hr_bpm ? `${activity.max_hr_bpm} bpm` : "—"} />
        </MetricGroupCard>
        <MetricGroupCard icon={<svg className="w-5 h-5 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>} title="Power">
          <MetricEntry label="Average" value={activity.avg_power_w ? `${activity.avg_power_w} W` : "—"} subtitle={activity.power_source === "hr_derived" ? "HR-derived" : undefined} />
          <MetricEntry label="Normalized" value={activity.np_power_w ? `${activity.np_power_w} W` : "—"} />
        </MetricGroupCard>
        <MetricGroupCard icon={<svg className="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>} title="Training Load">
          <MetricEntry label="TSS" value={activity.tss ? Math.round(activity.tss).toString() : "—"} tooltip={!ftpWatts && !activity.tss ? "Set FTP in Settings to calculate" : undefined} />
          <MetricEntry label="IF" value={activity.intensity_factor ? activity.intensity_factor.toFixed(2) : "—"} tooltip={!ftpWatts && !activity.intensity_factor ? "Set FTP in Settings to calculate" : undefined} />
          <MetricEntry label="W'bal Min" value={activity.wbal_min_pct != null ? `${Math.round(activity.wbal_min_pct)}%` : "—"} />
          {!ftpWatts && <div className="pt-3 border-t border-border"><p className="text-caption">Set FTP in Athlete profile to calculate training load metrics</p></div>}
        </MetricGroupCard>
      </div>



      {/* Performance Section */}
      <section className="mb-8">
        <SectionHeader title="Performance" subtitle="Time series data and zone distribution" />
        {CHARTS.map((chart) => {
          const { data, xKey, tickFormatter, ticks } = getChartData(chart);
          const hasData = data.some((d) => d[chart.dataKey as keyof typeof d] !== null);
          if (!hasData) return null;
          const values = data.map((d) => d[chart.dataKey as keyof typeof d] as number | null).filter((v): v is number => v !== null);
          const minVal = Math.min(...values), maxVal = Math.max(...values);
          const margin = (maxVal - minVal) * 0.1 || 5;
          const yMin = Math.max(0, Math.floor(minVal - margin)), yMax = Math.ceil(maxVal + margin);
          return (
            <ChartErrorBoundary key={chart.key} chartName={chart.label} height={200}>
              <ChartCard title={chart.label}
                action={<button onClick={() => toggleAxis(chart.key)} className={`px-3 py-1 text-xs font-medium rounded-full transition-fast ${axisModes[chart.key] === "distance" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"}`}>{axisModes[chart.key] === "distance" ? "Distance" : "Time"}</button>}
                onExpand={() => setExpandedChart(chart.key)}>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={data} onMouseLeave={handleChartLeave}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey={xKey} type="number" domain={['dataMin', 'dataMax']} tickFormatter={tickFormatter} ticks={ticks} interval={0} tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={{ stroke: "#d1d5db" }} tickLine={{ stroke: "#d1d5db" }} />
                    <YAxis domain={[yMin, yMax]} tick={{ fontSize: 12, fill: "#6b7280" }} axisLine={{ stroke: "#d1d5db" }} tickLine={{ stroke: "#d1d5db" }} label={{ value: chart.unit, angle: -90, position: "insideLeft", fontSize: 12, fill: "#6b7280" }} />
                    <RechartsTooltip content={({ active, payload }) => {
                      if (active && payload?.[0]?.payload) {
                        const p = payload[0].payload;
                        const pos = axisModes[chart.key] === "distance" ? findPositionByDistance(p.distance_m) : findPositionByElapsed(p.elapsed);
                        if (pos) setTimeout(() => setHoveredPosition(pos), 0);
                      }
                      if (!active || !payload?.length) return null;
                      const value = payload[0].value;
                      return <div style={{ backgroundColor: "white", border: "1px solid #e5e7eb", borderRadius: "8px", padding: "8px 12px", fontSize: "12px" }}>{chart.label}: {typeof value === "number" ? value.toFixed(2) : value}</div>;
                    }} />
                    <Line type="monotone" dataKey={chart.dataKey} stroke={chart.color} strokeWidth={2} dot={false} name={chart.label} />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            </ChartErrorBoundary>
          );
        })}


        {(activity.power_zone_times || activity.hr_zone_times) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {activity.power_zone_times && <ChartErrorBoundary chartName="Power Zones" height={200}><ZoneChart title="Power Zones" zoneTimes={activity.power_zone_times} zoneColors={POWER_ZONE_COLORS} /></ChartErrorBoundary>}
            {activity.hr_zone_times && <ChartErrorBoundary chartName="HR Zones" height={200}><ZoneChart title="HR Zones" zoneTimes={activity.hr_zone_times} zoneColors={HR_ZONE_COLORS} /></ChartErrorBoundary>}
          </div>
        )}
      </section>

      {/* Analysis Section */}
      <div ref={analysisSentinelRef} className="h-px" />
      {((activity.peaks && activity.peaks.length > 0) || (wbalData && wbalData.wbal_series.length > 0)) && (
        <section className="mb-8">
          <SectionHeader title="Analysis" subtitle="Power curve and W'bal depletion" />
          {analysisVisible ? (
            <>
              {activity.peaks && activity.peaks.length > 0 && <ChartErrorBoundary chartName="Power Curve" height={250}><ActivityPowerCurve peaks={activity.peaks} /></ChartErrorBoundary>}
              {wbalData && wbalData.wbal_series.length > 0 && <ChartErrorBoundary chartName="W'bal" height={200}><WbalChart wbalData={wbalData} findPositionByElapsed={findPositionByElapsed} setHoveredPosition={setHoveredPosition} /></ChartErrorBoundary>}
            </>
          ) : (
            <div className="space-y-6">
              <div className="bg-card rounded-lg border border-border p-4"><Skeleton className="h-5 w-32 mb-4" /><Skeleton className="h-[250px] w-full rounded" /></div>
              <div className="bg-card rounded-lg border border-border p-4"><Skeleton className="h-5 w-24 mb-4" /><Skeleton className="h-[200px] w-full rounded" /></div>
            </div>
          )}
        </section>
      )}



      {/* Delete Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete activity?</AlertDialogTitle>
            <AlertDialogDescription>This will permanently delete this activity and all its records. This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? <span className="flex items-center gap-2"><svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>Deleting…</span> : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <UploadToProviderDialog activityId={activityId} open={showUploadDialog} onOpenChange={setShowUploadDialog} />

      {/* Chart Expansion Modal */}
      {expandedChart && (() => {
        const chart = CHARTS.find((c) => c.key === expandedChart);
        if (!chart) return null;
        const resampled = resampleByDistance(records);
        const chartData = resampled.map((r, i) => ({ ...r, elapsed: i < timestamps.length ? timestamps[i] - firstTs : i * 10 }));
        return <ChartExpandModal chart={chart} data={chartData} axisMode={axisModes[chart.key]} onToggleAxis={() => toggleAxis(chart.key)} onClose={() => setExpandedChart(null)} formatDistance={(m) => formatDistance(m, unitSystem)} formatTime={(s) => formatTime(s)} ftpWatts={ftpWatts} lthrBpm={lthrBpm} />;
      })()}
    </div>
  );
}
