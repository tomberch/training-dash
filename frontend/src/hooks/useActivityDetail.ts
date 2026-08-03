import { useState, useEffect, useMemo, useCallback } from "react";
import type {
  Activity,
  GeoJSONFeatureCollection,
  SameRouteResponse,
  WbalResponse,
  ThresholdEntry,
} from "../api";
import {
  ApiError,
  fetchActivity,
  fetchActivityRecords,
  fetchSameRouteActivities,
  fetchActivityWbal,
  fetchThresholds,
  updateActivityTitle,
  generateActivityTitle,
} from "../api";
import type { FitRecord } from "../resampler";

export type AxisMode = "time" | "distance";

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

function positionsByDistance(
  features: GeoJSONFeatureCollection["features"]
): { distance_m: number; pos: [number, number] }[] {
  return features
    .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
    .map((f) => ({
      distance_m: f.properties.distance_m,
      pos: [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number],
    }));
}

export interface ChartDataPoint {
  distance_m: number;
  elapsed: number;
  speed_mps: number | null;
  hr_bpm: number | null;
  power_w: number | null;
  altitude_m: number | null;
}

export interface UseActivityDetailResult {
  // Loading/error state
  loading: boolean;
  error: Error | ApiError | null;
  setError: (error: Error | ApiError | null) => void;

  // Core data
  activity: Activity | null;
  setActivity: (activity: Activity | null) => void;
  geojson: GeoJSONFeatureCollection | null;
  sameRoute: SameRouteResponse | null;
  wbalData: WbalResponse | null;
  thresholds: ThresholdEntry[];

  // Derived data
  records: FitRecord[];
  timestamps: number[];
  firstTs: number;
  positions: [number, number][];
  posByDist: { distance_m: number; pos: [number, number] }[];
  posByElapsed: { elapsed: number; pos: [number, number] }[];

  // Thresholds
  applicableThreshold: ThresholdEntry | null;
  ftpWatts: number | null;
  lthrBpm: number | null;

  // Axis modes
  axisModes: { [key: string]: AxisMode };
  toggleAxis: (chartKey: string) => void;

  // Hover state
  hoveredPosition: [number, number] | null;
  setHoveredPosition: (pos: [number, number] | null) => void;
  findPositionByElapsed: (elapsed: number) => [number, number] | null;
  findPositionByDistance: (distance_m: number) => [number, number] | null;

  // Title editing
  isEditingTitle: boolean;
  setIsEditingTitle: (editing: boolean) => void;
  editedTitle: string;
  setEditedTitle: (title: string) => void;
  saveTitle: (title: string) => Promise<void>;

  // Title generation
  isGeneratingTitle: boolean;
  generateTitle: () => Promise<void>;

  // Chart expansion
  expandedChart: string | null;
  setExpandedChart: (chart: string | null) => void;
}

export function useActivityDetail(activityId: string): UseActivityDetailResult {
  // Core state
  const [activity, setActivity] = useState<Activity | null>(null);
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  // Related data
  const [sameRoute, setSameRoute] = useState<SameRouteResponse | null>(null);
  const [wbalData, setWbalData] = useState<WbalResponse | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdEntry[]>([]);

  // UI state
  const [axisModes, setAxisModes] = useState<{ [key: string]: AxisMode }>({
    speed: "time",
    hr: "time",
    power: "time",
    elevation: "time",
  });
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");
  const [isGeneratingTitle, setIsGeneratingTitle] = useState(false);
  const [expandedChart, setExpandedChart] = useState<string | null>(null);

  // Fetch all data in parallel
  useEffect(() => {
    setLoading(true);
    setWbalData(null);
    setError(null);

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
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, [activityId]);

  // Derived: records, timestamps, posByDist
  const records = useMemo(() => (geojson ? geojsonToRecords(geojson) : []), [geojson]);
  const timestamps = useMemo(() => (geojson ? geojsonToTimestamps(geojson) : []), [geojson]);
  const posByDist = useMemo(
    () => (geojson ? positionsByDistance(geojson.features) : []),
    [geojson]
  );
  const firstTs = useMemo(() => (timestamps.length > 0 ? timestamps[0] : 0), [timestamps]);

  // Derived: positions for map
  const positions = useMemo((): [number, number][] => {
    if (!geojson) return [];
    return geojson.features
      .filter((f) => f.geometry !== null && f.geometry.coordinates.length >= 2)
      .map((f) => [f.geometry!.coordinates[1], f.geometry!.coordinates[0]] as [number, number]);
  }, [geojson]);

  // Derived: applicable threshold for this activity's date
  const applicableThreshold = useMemo(() => {
    if (!activity || thresholds.length === 0) return null;
    const activityDate = new Date(activity.started_at).toISOString().split("T")[0];
    const applicable = thresholds.find((t) => t.effective_date <= activityDate);
    return applicable ?? thresholds[thresholds.length - 1];
  }, [activity, thresholds]);

  // Threshold values (FTP from wbal preferred over threshold)
  const ftpWatts = wbalData?.ftp_watts ?? applicableThreshold?.ftp_watts ?? null;
  const lthrBpm = applicableThreshold?.lthr_bpm ?? null;

  // Derived: position lookup by elapsed time
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

  // Position finders
  const findPositionByElapsed = useCallback(
    (elapsed: number): [number, number] | null => {
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
    },
    [posByElapsed]
  );

  const findPositionByDistance = useCallback(
    (distance_m: number): [number, number] | null => {
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
    },
    [posByDist]
  );

  // Actions
  const toggleAxis = useCallback((chartKey: string) => {
    setAxisModes((prev) => ({
      ...prev,
      [chartKey]: prev[chartKey] === "time" ? "distance" : "time",
    }));
  }, []);

  const saveTitle = useCallback(
    async (title: string) => {
      const updated = await updateActivityTitle(activityId, title);
      setActivity((prev) =>
        prev ? { ...prev, title: updated.title, title_source: updated.title_source } : prev
      );
      setIsEditingTitle(false);
    },
    [activityId]
  );

  const generateTitle = useCallback(async () => {
    setIsGeneratingTitle(true);
    try {
      const updated = await generateActivityTitle(activityId);
      setActivity((prev) =>
        prev ? { ...prev, title: updated.title, title_source: updated.title_source } : prev
      );
    } finally {
      setIsGeneratingTitle(false);
    }
  }, [activityId]);

  return {
    // Loading/error
    loading,
    error,
    setError,

    // Core data
    activity,
    setActivity,
    geojson,
    sameRoute,
    wbalData,
    thresholds,

    // Derived data
    records,
    timestamps,
    firstTs,
    positions,
    posByDist,
    posByElapsed,

    // Thresholds
    applicableThreshold,
    ftpWatts,
    lthrBpm,

    // Axis modes
    axisModes,
    toggleAxis,

    // Hover
    hoveredPosition,
    setHoveredPosition,
    findPositionByElapsed,
    findPositionByDistance,

    // Title editing
    isEditingTitle,
    setIsEditingTitle,
    editedTitle,
    setEditedTitle,
    saveTitle,

    // Title generation
    isGeneratingTitle,
    generateTitle,

    // Chart expansion
    expandedChart,
    setExpandedChart,
  };
}
