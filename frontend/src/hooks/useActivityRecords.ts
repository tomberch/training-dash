import { useState, useEffect, useMemo, useCallback } from "react";
import type { GeoJSONFeatureCollection } from "../api";
import { ApiError, fetchActivityRecords } from "../api";
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

export interface UseActivityRecordsResult {
  // Loading/error state
  loading: boolean;
  error: Error | ApiError | null;

  // Raw data
  geojson: GeoJSONFeatureCollection | null;

  // Derived data for charts
  records: FitRecord[];
  timestamps: number[];
  firstTs: number;

  // Derived data for map
  positions: [number, number][];
  posByDist: { distance_m: number; pos: [number, number] }[];
  posByElapsed: { elapsed: number; pos: [number, number] }[];

  // Axis modes for charts
  axisModes: { [key: string]: AxisMode };
  toggleAxis: (chartKey: string) => void;

  // Hover state (syncs map + charts)
  hoveredPosition: [number, number] | null;
  setHoveredPosition: (pos: [number, number] | null) => void;
  findPositionByElapsed: (elapsed: number) => [number, number] | null;
  findPositionByDistance: (distance_m: number) => [number, number] | null;

  // Chart expansion
  expandedChart: string | null;
  setExpandedChart: (chart: string | null) => void;
}

/**
 * Find the entry in `arr` whose value (extracted by `getValue`) is closest
 * to `target`. Returns `null` when the array is empty.
 */
function findNearest<T>(
  arr: T[],
  getValue: (item: T) => number,
  target: number,
): T | null {
  if (arr.length === 0) return null;
  let closest = arr[0];
  let minDiff = Math.abs(getValue(arr[0]) - target);
  for (const item of arr) {
    const diff = Math.abs(getValue(item) - target);
    if (diff < minDiff) {
      minDiff = diff;
      closest = item;
    }
  }
  return closest;
}

/**
 * Handles: time-series data for charts, positions for map, hover sync
 */
export function useActivityRecords(activityId: string): UseActivityRecordsResult {
  const [geojson, setGeojson] = useState<GeoJSONFeatureCollection | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  // UI state
  const [axisModes, setAxisModes] = useState<{ [key: string]: AxisMode }>({
    speed: "time",
    hr: "time",
    power: "time",
    elevation: "time",
  });
  const [hoveredPosition, setHoveredPosition] = useState<[number, number] | null>(null);
  const [expandedChart, setExpandedChart] = useState<string | null>(null);

  // Fetch records on mount/id change
  useEffect(() => {
    setLoading(true);
    setError(null);

    fetchActivityRecords(activityId)
      .then((g) => setGeojson(g))
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

  const findPositionByElapsed = useCallback(
    (elapsed: number): [number, number] | null => {
      const match = findNearest(posByElapsed, (p) => p.elapsed, elapsed);
      return match?.pos ?? null;
    },
    [posByElapsed]
  );

  const findPositionByDistance = useCallback(
    (distance_m: number): [number, number] | null => {
      const match = findNearest(posByDist, (p) => p.distance_m, distance_m);
      return match?.pos ?? null;
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

  return {
    loading,
    error,
    geojson,
    records,
    timestamps,
    firstTs,
    positions,
    posByDist,
    posByElapsed,
    axisModes,
    toggleAxis,
    hoveredPosition,
    setHoveredPosition,
    findPositionByElapsed,
    findPositionByDistance,
    expandedChart,
    setExpandedChart,
  };
}
